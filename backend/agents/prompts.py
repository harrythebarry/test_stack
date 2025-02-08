import datetime
import re
from typing import List, Tuple

from config import FAST_MODEL, MAIN_MODEL, FAST_PROVIDER
from agents.providers import LLM_PROVIDERS


async def chat_complete(
    system_prompt: str,
    user_prompt: str,
    fast: bool = True,
    temperature: float = 0.0,
) -> str:
    model = FAST_MODEL if fast else MAIN_MODEL
    return await LLM_PROVIDERS[FAST_PROVIDER]().chat_complete(
        system_prompt, user_prompt, model, temperature
    )


async def name_chat(seed_prompt: str) -> Tuple[str, str, str]:
    system_prompt = """
You are helping name a project and a session for a user building an app.

Given the initial prompt a user used to start the project, generate a name for the project and a name for the session.

Project name should be a short name for the app (be creative but concise).

Project description should be a short description/pitch of the app and what it aims to do (be creative but keep ~1 sentence).

Session name should be a short name for the user's current task (be creative but concise).

Respond only in the following format:
<output-format>
project: ...
project-description: ...
session: ...
</output-format>

<example>
project: Astro App
project-description: An app to empower astronomers to track celestial events.
session: Build the UI for Astro App
</example>
"""
    user_prompt = seed_prompt
    content = await chat_complete(system_prompt, user_prompt)
    try:
        project, project_description, session = re.search(
            r"project: (.*)\nproject-description: (.*)\nsession: (.*)", content
        ).groups()
    except Exception:
        print(f"Invalid response format: {content}")
        date = datetime.datetime.now().strftime("%Y-%m-%d")
        project, project_description, session = (
            f"Project {date}",
            f"A project created on{date}",
            f"Chat {date}",
        )
    return project, project_description, session


async def write_commit_message(content: str) -> str:
    msg = await chat_complete(
        """
You are a helpful assistant that writes commit messages for git. 

Given the following changes, write a commit message for the changes. 

- Respond only with the commit message.
- Do not use quotes or special characters.
- Do not use markdown formatting, newlines, or other formatting.
- Start with a verb, e.g. "Fixed", "Added", "Updated", etc.
""".strip(),
        content[:100000],
    )
    return re.sub(r"[^\w\s]+", "", msg)


async def pick_stack(seed_prompt: str, stack_titles: List[str], default: Tuple[str, str]) -> Tuple[str, str]:
    """
    Picks two stacks (frontend and backend) based on the seed_prompt.
    If unable to determine, defaults to the provided default stack for both frontend and backend.
    
    Args:
        seed_prompt (str): The initial prompt describing the project.
        stack_titles (List[str]): List of available stack titles from the database.
        default (str): The default stack title to use if parsing fails.
        
    Returns:
        Tuple[str, str]: A tuple containing the frontend and backend stack titles.
    """
    system_prompt = f"""
You are a helpful full-stack developer. The user wants TWO stacks:
 - A frontend stack (React, Next.js, Angular, etc.)
 - A backend stack (Python FastAPI, Node Express,  etc.)

Available Stacks:
{', '.join(stack_titles)}

User prompt: {repr(seed_prompt)}

Output must follow exactly this format:
<output-format>
frontend: ...
backend: ...
</output-format>

If the user only wants one stack or the information is unclear, repeat the stack in both 'frontend' and 'backend'.
"""

    content = await chat_complete(system_prompt, seed_prompt)
    
    # Parse the response to extract frontend and backend stacks
    try:
        frontend_match = re.search(r"frontend:\s*(.*)", content, re.IGNORECASE)
        backend_match = re.search(r"backend:\s*(.*)", content, re.IGNORECASE)
        
        if not frontend_match or not backend_match:
            raise ValueError("Unable to parse frontend or backend stack from response.")
        
        frontend = "Next.js Shadcn"
        backend = "fastapi"
    except Exception as e:
        # Fallback to default stack if parsing fails
        frontend = "nextjs"
        backend = "fastapi"
        # Optionally log the exception
        print(f"Error parsing stacks: {e}. Falling back to default stacks.")
    
    # Map the chosen stacks to actual stack titles from the database
    def map_stack(title_candidate: str, default_titles: str) -> str:
        stack_map = {t.lower().replace(" ", ""): t for t in stack_titles}
        norm = title_candidate.lower().replace(" ", "")
        return stack_map.get(norm, default_titles)
    
    frontend_mapped = map_stack(frontend, default[0])
    backend_mapped = map_stack(backend, default[1])
    
    return (frontend_mapped, backend_mapped)