import re

from .state import AgentState


def determine_starting_node(state: AgentState) -> str:
    """Determines the starting node based on countvar value."""
    if state.get("counter", 0) < 1:
        # state["counter"]+=1
        state["counter"] = 1
        return "system_planner"
    else:
        return "change_analyzer"
    





def parse_markdown_to_plaintext(md_text: str) -> str:
    """
    Convert a Markdown-like string to a plain text version:
      - Remove **bold** formatting
      - Remove inline/backtick code blocks
      - Trim spaces
      - Remove repeated newlines
      - (Optional) Remove bullet points
    """
    # 1. Remove bold markup **...**
    #    This pattern captures **something** and replaces it with 'something'
    parsed = re.sub(r'\*\*(.*?)\*\*', r'\1', md_text, flags=re.DOTALL)

    # 2. Remove inline code backticks `something`
    #    This pattern captures `something` including the backticks and removes them
    parsed = re.sub(r'`([^`]*)`', r'\1', parsed)

    # 3. Remove triple backticks ``` (often used for code blocks) or indentation
    #    If you want to remove entire code fences:
    parsed = re.sub(r'```+', '', parsed)

    # 4. Optionally remove bullet points like "- " or "* "
    #    If you still want bullet points, comment this step out.
    parsed = re.sub(r'^[\s]*[-*]\s+', '', parsed, flags=re.MULTILINE)

    # 5. Strip trailing and leading spaces on each line
    lines = [line.strip() for line in parsed.splitlines()]
    parsed = "\n".join(lines)

    # 6. Collapse multiple blank lines into one
    parsed = re.sub(r'\n\s*\n+', '\n\n', parsed)

    # 7. Finally, trim leading/trailing whitespace from the entire text
    parsed = parsed.strip()

    return parsed
