import modal
import aiohttp
import asyncio
import base64
import datetime
import uuid
import io
from typing import List, Optional, Tuple, AsyncGenerator, Union
from modal.volume import FileEntryType
from asyncio import Lock
from functools import lru_cache

from db.database import get_db
from db.models import Project, PreparedSandbox, Stack
from config import MODAL_APP_NAME

app = modal.App.lookup(MODAL_APP_NAME, create_if_missing=True)


IGNORE_PATHS = ["node_modules", ".git", ".next", "build", "git.log", "tmp"]


@lru_cache()
def _get_project_lock(project_id: int) -> Lock:
    return Lock()


class SandboxNotReadyException(Exception):
    pass


def _unique_id():
    return str(uuid.uuid4())


async def _is_url_up(url: str) -> bool:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                return response.status < 500
    except Exception:
        return False


async def _vol_to_paths(vol: modal.Volume):
    paths = []
    entries = await vol.listdir.aio("/", recursive=False)

    def _ends_with_ignore_path(path: str):
        path_parts = path.split("/")
        return any(
            part == ignore_path for ignore_path in IGNORE_PATHS for part in path_parts
        )

    async def _recurse(path: str):
        entries = await vol.listdir.aio(path, recursive=False)
        for entry in entries:
            if _ends_with_ignore_path(entry.path):
                continue
            if entry.type == FileEntryType.DIRECTORY:
                await _recurse(entry.path)
            else:
                paths.append(entry.path)

    for entry in entries:
        if _ends_with_ignore_path(entry.path):
            continue
        if entry.type == FileEntryType.DIRECTORY:
            await _recurse(entry.path)
        else:
            paths.append(entry.path)

    return paths


def _strip_app_prefix(path: str) -> str:
    if path.startswith("/app/"):
        return path[len("/app/") :]
    return path


class ModalSandbox:
    def __init__(self, project_id: int, sb: modal.Sandbox, vol: modal.Volume):
        self.project_id = project_id
        self.sb = sb
        self.vol = vol
        self.ready = False

    async def is_up(self):
        tunnels = await self.sb.tunnels.aio()
        tunnel_url = tunnels[3000].url
        return await _is_url_up(tunnel_url)

    async def wait_for_up(self):
        while True:
            if await self.is_up():
                break
            await asyncio.sleep(1)
        self.ready = True

    async def get_file_paths(self) -> List[str]:
        paths = await _vol_to_paths(self.vol)
        return sorted(["/app/" + path for path in paths])

    async def run_command(self, command: str, workdir: Optional[str] = None) -> str:
        try:
            proc = await self.sb.exec.aio(
                "sh", "-c", command, workdir=workdir or "/app"
            )
            await proc.wait.aio()
            return (await proc.stdout.read.aio()) + (await proc.stderr.read.aio())
        except Exception as e:
            return f"Error: {e}"

    async def run_command_stream(
        self, command: str, workdir: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        proc = await self.sb.exec.aio("sh", "-c", command, workdir=workdir or "/app")
        async for chunk in proc.stderr:
            yield chunk

    async def commit_changes(self, commit_message: str):
        await self.run_command(f"git add -A && git commit -m {repr(commit_message)}")
        await self.run_command(
            'git log --pretty="%h|%s|%aN|%aE|%aD" -n 50 > /app/git.log'
        )

    async def read_file_contents(
        self, path: str, does_not_exist_ok: bool = False
    ) -> str:
        path = _strip_app_prefix(path)
        content = []
        try:
            async for chunk in self.vol.read_file.aio(path):
                content.append(chunk.decode("utf-8"))
        except FileNotFoundError as e:
            if does_not_exist_ok:
                return ""
            raise e
        return "".join(content)

    async def has_file(self, path: str):
        try:
            # Attempt to get first chunk of the file
            async for _ in self.vol.read_file.aio(_strip_app_prefix(path)):
                return True  # If we can read any chunk, the file exists
            return True  # Empty file case
        except FileNotFoundError:
            return False

    async def stream_file_contents(
        self, path: str, binary_mode: bool = False
    ) -> AsyncGenerator[Union[str, bytes], None]:
        path = _strip_app_prefix(path)
        try:
            async for chunk in self.vol.read_file.aio(path):
                if binary_mode:
                    yield chunk
                else:
                    yield chunk.decode("utf-8")
        except FileNotFoundError as e:
            raise e

    @classmethod
    async def terminate_project_resources(cls, project: Project):
        if project.modal_sandbox_id:
            sb = await modal.Sandbox.from_id.aio(project.modal_sandbox_id)
            try:
                await sb.terminate.aio()
            except Exception as e:
                print("Error terminating sandbox", e)

    @classmethod
    async def get_project_file_contents(
        cls, project: Project, path: str
    ) -> Optional[bytes]:
        if vol_id := project.modal_volume_label:
            vol = await modal.Volume.lookup.aio(label=vol_id)
            try:
                data = b""
                async for chunk in vol.read_file.aio(_strip_app_prefix(path)):
                    data += chunk
            except FileNotFoundError:
                return None
            else:
                return data
        return None

    async def write_file(self, path: str, content: str):
        files = [(path, content)]
        files_data = []
        for path, content in files:
            encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
            files_data.append((path, encoded_content))

        # Note: This hacky approach helps with auto-reload which doesn't work with modal.Volume.batch_upload
        python_cmd = f"""
import os
import base64

files = {str(files_data)}

for path, base64_content in files:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(base64.b64decode(base64_content).decode('utf-8'))
"""
        proc = await self.sb.exec.aio(
            "python3",
            "-c",
            python_cmd,
            workdir="/app",
        )
        await proc.wait.aio()

    @classmethod
    async def write_project_file(
        cls, project: Project, path: str, content: str
    ) -> None:
        if vol_id := project.modal_volume_label:
            vol = await modal.Volume.lookup.aio(label=vol_id)
            path = _strip_app_prefix(path)
            with io.BytesIO(content.encode("utf-8")) as f:
                async with vol.batch_upload(force=True) as batch:
                    batch.put_file(f, path)

    @classmethod
    async def destroy_project_resources(cls, project: Project):
        if project.modal_sandbox_id:
            sb = await modal.Sandbox.from_id.aio(project.modal_sandbox_id)
            try:
                await sb.terminate.aio()
            except Exception as e:
                print("Error terminating sandbox", e)
        if project.modal_volume_label:
            try:
                await modal.Volume.delete.aio(label=project.modal_volume_label)
            except Exception as e:
                print("Error deleting volume", e)

    @classmethod
    async def get_or_create(
        cls, project_id: int, create_if_missing: bool = True
    ) -> "ModalSandbox":
        lock = _get_project_lock(project_id)
        try:
            await lock.acquire()
            db = next(get_db())
            project = db.query(Project).filter(Project.id == project_id).first()
            stack = db.query(Stack).filter(Stack.id == project.stack_id).first()
            if not project or not stack:
                raise SandboxNotReadyException(
                    f"Project or stack not found (project={project_id})"
                )

            if not project.modal_volume_label:
                existing_psb = (
                    db.query(PreparedSandbox)
                    .filter(PreparedSandbox.stack_id == stack.id)
                    .first()
                )
                if not existing_psb:
                    raise SandboxNotReadyException(
                        f"No prepared sandbox found for stack (stack={stack.id}, project={project_id})"
                    )

                project.modal_volume_label = existing_psb.modal_volume_label
                db.delete(existing_psb)
                db.commit()
                print(
                    f"Using existing prepared sandbox for project (psb={existing_psb.id}, vol={project.modal_volume_label}) -> (project={project_id})"
                )

            vol = await modal.Volume.lookup.aio(label=project.modal_volume_label)

            if project.modal_sandbox_id:
                sb = await modal.Sandbox.from_id.aio(project.modal_sandbox_id)
                poll_code = await sb.poll.aio()
                return_code = sb.returncode
                sb_is_up = ((poll_code is None) or (return_code is None)) or (
                    poll_code == 0 and return_code == 0
                )
            else:
                sb_is_up = False
            if not sb_is_up:
                if not create_if_missing:
                    raise SandboxNotReadyException(
                        f"Sandbox is not ready for project (project={project_id})"
                    )
                print(
                    f"Booting new sandbox for project (project={project_id}, prev_sandbox={project.modal_sandbox_id})",
                )

                expires_in = 60 * 60
                image = modal.Image.from_registry(stack.from_registry, add_python=None)
                sb = await modal.Sandbox.create.aio(
                    "sh",
                    "-c",
                    stack.sandbox_start_cmd,
                    app=app,
                    volumes={"/app": vol},
                    image=image,
                    encrypted_ports=[3000],
                    timeout=expires_in,
                    cpu=0.125,
                    memory=1024 * 2,
                )
                project.modal_sandbox_id = sb.object_id
                project.modal_sandbox_last_used_at = datetime.datetime.now()
                project.modal_sandbox_expires_at = (
                    datetime.datetime.now() + datetime.timedelta(seconds=expires_in)
                )
                db.commit()
                await sb.set_tags.aio(
                    {"project_id": str(project_id), "app": "prompt-stack"}
                )
                print(
                    f"Booted new sandbox for project (sb={sb.object_id}, vol={project.modal_volume_label}, project={project_id})"
                )
            else:
                print("Using existing sandbox for project", project.id)
                sb = await modal.Sandbox.from_id.aio(project.modal_sandbox_id)

            return cls(project_id, sb, vol)
        finally:
            lock.release()

    @classmethod
    async def prepare_sandbox(cls, stack: Stack) -> Tuple["ModalSandbox", str]:
        vol_id = f"prompt-stack-vol-{_unique_id()}"
        vol = modal.Volume.from_name(vol_id, create_if_missing=True)
        image = modal.Image.from_registry(stack.from_registry, add_python=None)
        sb = await modal.Sandbox.create.aio(
            "sh",
            "-c",
            stack.sandbox_init_cmd,
            app=app,
            volumes={"/app": vol},
            image=image,
            timeout=5 * 60,
            cpu=0.125,
            memory=256,
        )
        await sb.set_tags.aio({"app": "prompt-stack"})
        await sb.wait.aio()
        return sb, vol_id
