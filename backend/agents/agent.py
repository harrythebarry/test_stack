# agent.py

import re
import json
from typing import AsyncGenerator, List, Optional, Dict

from pydantic import BaseModel

from sandbox.local_docker_sandbox import LocalDockerSandbox
from db.models import Project, Stack, User, UserType
from sandbox.sandbox import BaseSandbox
from agents.prompts import chat_complete, write_commit_message
from agents.diff import remove_file_changes, DiffApplier
from agents.providers import AgentTool, LLM_PROVIDERS
from config import MAIN_MODEL, MAIN_PROVIDER

USER_TYPE_STYLES: Dict[UserType, str] = {
    UserType.WEB_DESIGNER: """User Type: Web Designer
Experience: Familiar with web design concepts and basic HTML/CSS
Communication Style: Use design and UI/UX terminology. Explain technical concepts in terms of visual and user experience impact.
Code Explanations: Focus on how changes affect the look and feel. Provide context for any backend changes.""",
    UserType.LEARNING_TO_CODE: """User Type: Learning to Code
Experience: Basic programming knowledge, learning fundamentals
Communication Style: Break down complex concepts. Use simple terms and provide explanations for technical decisions.
Code Explanations: Include brief comments explaining what each major code block does. Point out patterns and best practices.""",
    UserType.EXPERT_DEVELOPER: """User Type: Expert Developer
Experience: Proficient in full-stack development
Communication Style: Use technical terminology freely. Focus on architecture and implementation details.
Code Explanations: Can skip basic explanations. Highlight advanced patterns and potential edge cases.""",
}


class ChatMessage(BaseModel):
    """
    Represents a single user or assistant message in the conversation.
    """
    id: Optional[int] = None
    role: str
    content: str
    images: Optional[List[str]] = None


class PartialChatMessage(BaseModel):
    """
    Represents a chunk of assistant output that can be streamed
    (like delta tokens or partial final text).
    """
    role: str
    delta_content: str = ""
    delta_thinking_content: str = ""  # if you want to separate "thinking" from visible text


def build_run_command_tool(sandbox: Optional[BaseSandbox] = None):
    """
    Example of a tool that can run commands in the project sandbox.
    """
    async def func(command: str, workdir: Optional[str] = None) -> str:
        if sandbox is None:
            return "This environment is still booting up! Try again in a minute."
        result = await sandbox.run_command(command, workdir=workdir)
        print(f"$ {command} -> {result[:20]}")
        if result == "":
            result = "<empty response>"
        return result

    return AgentTool(
        name="run_command",
        description="Run a shell command in the project sandbox. Use for installing packages or reading the content of files. NEVER use to modify the content of files.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "workdir": {
                    "type": "string",
                    "description": "The directory to run the command in. Defaults to /app",
                },
            },
            "required": ["command"],
        },
        func=func,
    )


def build_navigate_to_tool(agent: "Agent"):
    """
    Example of a tool that can "navigate" the user’s browser in your UI.
    """
    async def func(path: str):
        agent.working_page = path
        print(f"Navigating user to {path}")
        return "Navigating user to " + path

    return AgentTool(
        name="navigate_to",
        description="Trigger the user's browser to navigate to the given path (e.g. /settings)",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
            },
            "required": ["path"],
        },
        func=func,
    )


########################
# System Prompts
########################

SYSTEM_PLAN_PROMPT = """
You are a full-stack expert developer on the platform Spark Stack. You are given a project and a sandbox to develop in and are helping PLAN the next steps. You do not write code and only provide advice as a Senior Engineer.

They will be able to edit files, run arbitrary commands in the sandbox, and navigate the user's browser.

<project>
{project_text}
</project>

<user>
{user_text}
</user>

<stack>
{stack_text}
</stack>

<project-files>
{files_text}
</project-files>

<git-log>
{git_log_text}
</git-log>

Answer the following questions:
1. What is being asked by the most recent message?
1a. Is this a general question, command to build something, etc.?
2. Which files are relevant to the question or would be needed to perform the request?
2a. What page should the user be navigated to to see/verify the change? (e.g. /settings)
2b. If there's weird behavior, what files should we cat to double check?
3. What commands might you need to run?
3a. Packages needed?
4. For EACH stack-specific tip, what to keep in mind or how does it adjust your plan?
5. Sequence of steps to do it? (tools/commands -> generate files -> conclusion)
6. Verify your plan with respect to the user’s knowledge level.
7. Output in markdown with h3 headings, no code blocks, just ADVICE ONLY.
"""

SYSTEM_EXEC_PROMPT = """
You are a full-stack expert developer on the platform Spark Stack. You are given a <project> and a <stack> sandbox to develop in and a <plan> from a senior engineer.

<commands>
You can run shell commands in the sandbox.
- e.g. `npm install`, `cat`, `ls`, `git`, etc.
- DO NOT USE it to modify files (like `vim`, `nano`, `touch`).
</commands>

<formatting-instructions>
Respond in plain markdown. Use special codeblocks to update files:
  - The first line: `// /path/to/file.ext`
  - Then `// ... existing code ...`
  - Then your changes, etc.
No indentation for the ``` lines. That’s your entire code update block.

The system will automatically apply diffs after the final response, then commit the changes with git.
</formatting-instructions>

<project>
{project_text}
</project>

<user>
{user_text}
</user>

<stack>
{stack_text}
</stack>

<tips>
- Use the `simple-code-block-template` style for file modifications.
- No need to show `npm run dev`.
- The user can see changes in a preview window.
</tips>

Follow the <plan>.
"""

SYSTEM_FOLLOW_UP_PROMPT = """
You are a full-stack developer helping someone build a webapp.

You are given a conversation between the user and the assistant for building <project> on <stack>.

Your job is to suggest 3 follow up prompts the user might ask next.

<output-format>
<follow-ups>
- ...prompt...
- ...prompt...
- ...prompt...
</follow-ups>
</output-format>

<example>
<follow-ups>
- Add a settings page
- Improve the styling of the homepage
- Add more dummy content
</follow-ups>
</example>

<tips>
- Keep them short, <10 words, related to user’s conversation.
- Do not propose devops or unrelated tasks.
- Plain text only, in <follow-ups> tags.
</tips>

<project>
{project_text}
</project>

<stack>
{stack_text}
</stack>

Respond with <follow-ups> tags only.
"""


########################
# Helper functions
########################

def _parse_follow_ups(content: str) -> List[str]:
    """
    Extract lines like:
    <follow-ups>
    - ...
    - ...
    - ...
    </follow-ups>
    """
    match = re.search(r"<follow-ups>(.*?)</follow-ups>", content, re.DOTALL)
    if not match:
        return []
    # parse bullet lines
    follow_ups = re.findall(r"\s*\-\s*(.+)", match.group(1))
    return follow_ups


def _append_last_user_message(messages: List[dict], text: str) -> None:
    """
    A utility to append 'text' to the last user message.
    """
    last_user = next((m for m in reversed(messages) if m["role"] == "user"), None)
    if not last_user:
        raise ValueError("No user message found in messages!")
    # If content is a list, append a text block
    if isinstance(last_user["content"], list):
        last_user["content"].append({"type": "text", "text": text})
    else:
        # or if it's plain text, just concatenate
        last_user["content"] += "\n\n" + text

class ResponseFormat(BaseModel):
    file_path: str
    content: str
    
class LLMResponseFormat(BaseModel):
    response_format: List[ResponseFormat]
########################
# Agent Class
########################

class Agent:
    """
    A multi-phase agent for a project. It can do single-phase or multi-phase:
      - Phase 1: produce BACKEND code + doc
      - Phase 2: produce FRONTEND code referencing the doc
    """

    def __init__(self, project: Project, stack: Stack, user: User):
        """
        The 'stack' here might be a single stack. 
        If you have multiple stacks (FE + BE), adapt as needed 
        (like self.backend_stack, self.frontend_stack).
        """
        self.project = project
        self.user = user
        self.stack = stack
        self.sandbox = LocalDockerSandbox
        self.working_page = None

        # Multi-phase doc
        self.backend_doc: Optional[str] = None

    def set_sandbox(self, sandbox: BaseSandbox):
        """
        Attach a sandbox object so we can run commands, etc.
        """
        self.sandbox = sandbox

    async def _handle_tool_call(self, tools: List[AgentTool], tool_call) -> str:
        """
        For LLM tool calls (like run_command), find the right tool and run it.
        """
        tool_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)
        tool = next((t for t in tools if t.name == tool_name), None)
        if not tool:
            raise ValueError(f"Unknown tool called: {tool_name}")
        return await tool.func(**arguments)

    def _get_project_text(self) -> str:
        return (
            f"Name: {self.project.name}\n"
            f"Sandbox Status: {'Ready' if self.sandbox else 'Booting...'}\n"
            f"Custom Instructions: {self.project.custom_instructions}"
        )

    def _get_user_text(self) -> str:
        """
        Insert user-type style info
        """
        return USER_TYPE_STYLES.get(
            self.user.user_type, USER_TYPE_STYLES[UserType.WEB_DESIGNER]
        )

    ########################
    # Multi-Phase Support
    ########################

    async def multi_phase_step(
        self,
        messages: List[ChatMessage],
        sandbox_file_paths: Optional[List[str]] = None,
        sandbox_git_log: Optional[str] = None,
    ) -> AsyncGenerator[PartialChatMessage, None]:
        """
        Example of a 2-phase approach:
          1) Generate BACKEND code + doc
          2) Use that doc to generate FRONTEND code
        If you truly have 2 different sandboxes, you'd switch them out in each phase or have 2 Agent instances.
        """
        # Phase 1: "BACKEND code + doc"
        phase1_plan = "PHASE 1: Produce BACKEND code. Include 'BACKEND DOC:' in your final message describing new endpoints."
        async for partial in self._run_phase(messages, phase1_plan, sandbox_file_paths, sandbox_git_log, store_backend_doc=True):
            yield partial

        # Phase 2: "FRONTEND code" referencing the doc
        phase2_plan = f"PHASE 2: Use this BACKEND DOC: {self.backend_doc} to produce FRONTEND code changes."
        async for partial in self._run_phase(messages, phase2_plan, sandbox_file_paths, sandbox_git_log, store_backend_doc=False):
            yield partial


    async def _run_phase(
        self,
        messages: List[ChatMessage],
        phase_instructions: str,
        sandbox_file_paths: Optional[List[str]],
        sandbox_git_log: Optional[str],
        store_backend_doc: bool
    ) -> AsyncGenerator[PartialChatMessage, None]:
        """
        Reuses the same planning + execution pipeline, but inserts `phase_instructions` 
        as part of the plan.
        """
        # 1) Convert the normal plan
        files_text = "\n".join(sandbox_file_paths or ["(still booting)"])
        git_log_text = "(still booting)"
        if sandbox_git_log:
            git_log_text = await self._git_log_text(sandbox_git_log)

        project_text = self._get_project_text()
        stack_text = self.stack.prompt
        user_text = self._get_user_text()

        # We do the 'plan' step but insert "phase_instructions" in the user message
        plan_content = ""
        async for chunk in self._plan(
            messages,
            project_text=project_text,
            git_log_text=git_log_text,
            stack_text=stack_text,
            files_text=files_text,
            user_text=user_text,
            extra_instructions=phase_instructions
        ):
            yield chunk
            plan_content += chunk.delta_thinking_content

        # 2) Then do the 'exec' step with the final plan
        system_prompt = SYSTEM_EXEC_PROMPT.format(
            project_text=project_text,
            stack_text=stack_text,
            user_text=user_text,
        )

        # Convert messages to provider format
        exec_messages = [
            {"role": "system", "content": system_prompt},
            *[
                {
                    "role": m.role,
                    "content": [{"type": "text", "text": m.content}]
                    + (
                        []
                        if not m.images
                        else [{"type": "image_url", "image_url": {"url": img}} for img in m.images]
                    ),
                }
                for m in messages
            ],
        ]
        _append_last_user_message(
            exec_messages,
            (
                f"---\n<project-files>\n{files_text}\n</project-files>"
                f"\n<plan>\n{plan_content}\n</plan>\n---"
            )
        )

        # Tools
        tools = [build_run_command_tool(self.sandbox), build_navigate_to_tool(self)]

        model = LLM_PROVIDERS[MAIN_PROVIDER]()
        diff_applier = DiffApplier(self.sandbox)
        final_response_text = ""

        async for chunk in model.chat_complete_with_tools(
            messages=exec_messages,
            tools=tools,
            model=MAIN_MODEL,
            temperature=0.0,
        ):
            # If it's partial content, we yield it out to the user
            if chunk["type"] == "content":
                text_part = chunk["content"]
                final_response_text += text_part
                # Also feed diffs to DiffApplier
                diff_applier.ingest(text_part)
                yield PartialChatMessage(
                    role="assistant",
                    delta_content=text_part
                )
            elif chunk["type"] == "tool_calls":
                # Tools were called, do nothing special except maybe yield a blank
                yield PartialChatMessage(role="assistant", delta_content="\n\n")

        # 3) Now apply the diffs to the sandbox
        await diff_applier.apply()

        # 4) If we are storing the BACKEND DOC, parse it out
        #    e.g. look for "BACKEND DOC:" up to triple backticks or end
        if store_backend_doc:
            doc_match = re.search(r"BACKEND DOC:(.*?)(```|$)", final_response_text, re.DOTALL)
            if doc_match:
                self.backend_doc = doc_match.group(1).strip()

 


    ########################
    # Existing Single-Phase Step
    ########################

        

    async def step(
        self,
        messages: List[ChatMessage],
        file_paths: Optional[List[str]] = None,
        sandbox_git_log: Optional[str] = None,
        backend_doc: Optional[str] = None,
    ) -> AsyncGenerator[PartialChatMessage, None]:
        """
        The original single-phase approach (plan -> exec).
        If you want to always do the multi-phase approach, 
        you can remove or rename this method.
        """
        # Provide an initial empty partial so the UI can mark 'assistant is responding'
        yield PartialChatMessage(role="assistant", delta_content="")

        if file_paths is not None:
            files_text = "\n".join(file_paths)
        if sandbox_git_log:
            git_log_text = await self._git_log_text(sandbox_git_log)
        else:
            git_log_text = "Sandbox is still booting..."

        project_text = self._get_project_text()
        stack_text = self.stack.prompt
        user_text = self._get_user_text()

        # 1) Plan
        plan_content = ""
        async for chunk in self._plan(
            messages=messages,
            project_text=project_text,
            git_log_text=git_log_text,
            stack_text=stack_text,
            files_text=files_text,
            user_text=user_text,
            extra_instructions=f"BACKEND DOC: {backend_doc}" if backend_doc else ""
        ):
            yield chunk
            plan_content += chunk.delta_thinking_content
            
        print(f"plan_content: {plan_content}")

        # 2) Exec
        system_prompt = SYSTEM_EXEC_PROMPT.format(
            project_text=project_text,
            stack_text=stack_text,
            user_text=user_text,
        )

        exec_messages = [
            {"role": "system", "content": system_prompt},
            *[
                {
                    "role": msg.role,
                    "content": [{"type": "text", "text": msg.content}]
                    + (
                        []
                        if not msg.images
                        else [{"type": "image_url", "image_url": {"url": i}} for i in msg.images]
                    ),
                }
                for msg in messages
            ],
        ]
        _append_last_user_message(
            exec_messages,
            (
                f"---\n<project-files>\n{files_text}\n</project-files>"
                f"\n<plan>\n{plan_content}\n</plan>\n---"
            )
        )

        tools = [build_run_command_tool(self.sandbox), build_navigate_to_tool(self)]
        model = LLM_PROVIDERS[MAIN_PROVIDER]()


        final_response_text = ""

        async for chunk in model.chat_complete_with_tools(
            messages=exec_messages,
            tools=tools,
            model=MAIN_MODEL,
            temperature=0.0,
            response_format=LLMResponseFormat
        ):
            diff_applier = DiffApplier(self.sandbox)
            if chunk["type"] == "content":
                text_part = chunk["content"]
                final_response_text += text_part
                diff_applier.ingest(text_part)
                yield PartialChatMessage(role="assistant", delta_content=text_part)
            elif chunk["type"] == "tool_calls":
                # e.g. run_command or navigate_to
                yield PartialChatMessage(role="assistant", delta_content="\n\n")

        print(f"final_response_text: {final_response_text}")
        # apply diffs
        
        await diff_applier.apply()
        
        


    ########################
    # Internal Plan + Helpers 
    ########################

    async def _plan(
        self,
        messages: List[ChatMessage],
        project_text: str,
        git_log_text: str,
        stack_text: str,
        files_text: str,
        user_text: str,
        extra_instructions: str = ""
    ) -> AsyncGenerator[PartialChatMessage, None]:
        """
        The 'planning' half: Summarize steps, no code blocks, etc.
        We can insert 'extra_instructions' for multi-phase usage.
        """
        # Build conversation_text from user messages
        conversation_text = "\n\n".join(
            [f"<msg>{remove_file_changes(m.content)}</msg>" for m in messages]
        )

        # system prompt
        system_prompt = SYSTEM_PLAN_PROMPT.format(
            project_text=project_text,
            user_text=user_text,
            stack_text=stack_text,
            files_text=files_text,
            git_log_text=git_log_text,
        )

        # If we have extra instructions (like "PHASE 1: produce backend code..."),
        # we can just append them to the user's last message
        planning_messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"{conversation_text}\n\n{extra_instructions}\n\nProvide the plan in the correct format only."}
                ]
            },
        ]

        model = LLM_PROVIDERS[MAIN_PROVIDER]()
        async for chunk in model.chat_complete_with_tools(
            messages=planning_messages,
            tools=[],  # no tools for planning
            model=MAIN_MODEL,
            temperature=0.0,
        ):
            if chunk["type"] == "content":
                # yield partial "thinking" content
                yield PartialChatMessage(
                    role="assistant", 
                    delta_thinking_content=chunk["content"]
                )

    async def _git_log_text(self, git_log: str) -> str:
        """
        Convert the raw lines of 'hash|msg|author|etc' into a simpler text block.
        """
        lines = []
        for line in git_log.split("\n"):
            if not line.strip():
                continue
            parts = line.split("|")
            if len(parts) >= 2:
                short_hash = parts[0]
                msg = parts[1]
                lines.append(f"{short_hash}: {msg}")
        return "\n".join(lines)


    ########################
    # Follow Ups
    ########################

    async def suggest_follow_ups(self, messages: List[ChatMessage]) -> List[str]:
        """
        Queries the LLM for 3 next possible user questions, embedded in <follow-ups> tags.
        """
        conversation_text = "\n\n".join(
            [f"<{m.role}>{remove_file_changes(m.content)}</{m.role}>" for m in messages]
        )
        project_text = self._get_project_text()
        stack_text = self.stack.prompt
        system_prompt = SYSTEM_FOLLOW_UP_PROMPT.format(
            project_text=project_text,
            stack_text=stack_text,
        )
        content = await chat_complete(system_prompt, conversation_text[-10000:])
        
        # parse bullet lines from <follow-ups> ... </follow-ups>
        try:
            matches = re.search(r"<follow-ups>(.*?)</follow-ups>", content, re.DOTALL)
            if not matches:
                return []
            lines = re.findall(r"^\-\s*(.*)", matches.group(1), re.MULTILINE)
            return [ln.strip() for ln in lines if ln.strip()]
        except Exception:
            print("Error parsing follow-ups from LLM content:", content)
            return []
