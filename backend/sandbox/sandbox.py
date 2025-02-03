# backend/sandbox/sandbox.py

import asyncio
import traceback
from typing import Optional, List, Tuple

class SandboxNotReadyException(Exception):
    pass

class BaseSandbox:
    """
    Abstract base class for a sandbox environment.
    """
    def __init__(self, project_id: int):
        self.project_id = project_id

    async def wait_for_up(self):
        """
        Wait until the sandbox is fully up and accessible.
        """
        raise NotImplementedError

    async def get_file_paths(self) -> List[str]:
        raise NotImplementedError

    async def read_file_contents(self, path: str, does_not_exist_ok=False) -> str:
        raise NotImplementedError

    async def run_command(self, command: str, workdir: Optional[str] = None) -> str:
        raise NotImplementedError

    async def has_file(self, path: str) -> bool:
        """
        Optional convenience check if a file exists.
        """
        try:
            await self.read_file_contents(path, does_not_exist_ok=False)
            return True
        except:
            return False

    async def commit_changes(self, commit_message: str):
        raise NotImplementedError

  