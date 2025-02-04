# sandbox/local_docker_sandbox.py

import os
import asyncio
import base64
import time
import docker
import aiohttp
from docker.errors import NotFound
from typing import AsyncGenerator, Union

import requests
from db.models import Project, Service, ServiceType
from db.database import get_db
from config import _int_env
from sqlalchemy import inspect

# We define a starting port, e.g. 4000
DOCKER_PORT_START = _int_env("DOCKER_PORT_START", 4000)

class LocalDockerSandbox:
    """
    Manages a local Docker container for a single 'Service'.
    """
    def __init__(self, service: Service):
        """
        Instead of project_id, we store the entire 'Service' DB row.
        """
        self.service = service
        print("Service is atteched : ", not inspect(service).detached)
        self.client = docker.from_env()
        # container name can incorporate service.id
        self.container_name = f"sparkstack_svc_{service.id}"
        self.container = None
        self.ready = False

    async def create_or_get_container(self, image: str, start_command: str):
        """
        Create (or attach to) a local Docker container for this service.
        - We pick a local port from DOCKER_PORT_START + service.id, 
          or use an existing 'docker_port' if set in the DB.
        """
        db = next(get_db())
        db.merge(self.service)
        if not self.service.docker_port:
            # Example: just do "base + service.id"
            self.service.docker_port = DOCKER_PORT_START + self.service.id

        host_port = self.service.docker_port

        try:
            # Check if container already exists
            self.container = self.client.containers.get(self.container_name)
            # If it exists but is not running, start it
            if self.container.status != "running":
                self.container.start()
        except NotFound:
            # Create a new container
            self.container = self.client.containers.run(
                image=image,
                name=self.container_name,
                command=["sh", "-c", start_command],
                detach=True,
                ports={"3000/tcp": host_port},  # Map port 3000 in container -> 'host_port'
                tty=True,
            )

        # Store container ID in DB
        self.service.docker_container_id = self.container.id
        print("commiting changes: ", self.container.id, self.service.docker_port)
        db.commit()


    async def wait_for_up(self):
        while True:
            if await self.is_up():
                self.ready = True
                break
            time.sleep(1)
        # once up, store in DB
        url = f"http://localhost:{self.service.docker_port}"
        db = next(get_db())
        db.merge(self.service)
        self.service.preview_url = url
        db.commit()
       

    async def is_up(self) -> bool:
        if not self.container:
            return False
        # Try to connect to localhost:service.docker_port
        if not self.service.docker_port:
            return False
        return await self._is_port_open("127.0.0.1", self.service.docker_port)

    async def _is_port_open(self, host, port):
        try:
            reader, writer = await asyncio.open_connection(host, port)
            writer.close()
            await writer.wait_closed()
            return True
        except:
            return False

    async def run_command(self, command: str, workdir=None) -> str:
        if not self.container:
            return "Container not started yet."
        final_cmd = f"cd {workdir or '/app'} && {command}"
        result = self.container.exec_run(f"sh -c '{final_cmd}'")
        return result.output.decode("utf-8", errors="ignore")

    async def get_file_paths(self):
        """
        Retrieves the file paths within the service container.
        Supports both backend (Python/FastAPI) and frontend (Next.js/React/Angular).
        """
        # Determine the correct working directory
        if self.service.service_type == ServiceType.FRONTEND:
            workdir = "/frontend"
        else:
            workdir = "/app"  # Default to backend directory

        # Try to fetch the file paths
        out = await self.run_command("find . -type f", workdir=workdir)
        
        # If there's an error, return an empty list and log the error
        if "can't cd" in out or "No such file" in out:
            print(f"[ERROR] Unable to access {workdir} in container: {out}")
            return []

        lines = out.strip().split("\n")

        # Ignore common unwanted directories
        ignore_list = [
            "node_modules",
            ".git",
            ".next",
            "build",
            "tmp",
            "__pycache__",  # Python cache directories
            ".venv",       # Virtual environments
            "venv",
            "env",
            ".mypy_cache",
            ".pytest_cache",
            ".cache",
            ".DS_Store",   # macOS specific
            "Thumbs.db",   # Windows specific
        ]

        # Extensions to ignore (Python intermediate files)
        python_intermediate_extensions = [".pyc", ".pyd", ".pyo", ".pyi"]

        def should_ignore(file_path):
            if any(ig in file_path for ig in ignore_list):
                return True
            _, ext = os.path.splitext(file_path)
            if ext in python_intermediate_extensions:
                return True
            return False

        return sorted(
            f"{workdir}{l[1:]}" for l in lines if l.strip() and not should_ignore(l)
        )


    async def read_file_contents(self, path: str, does_not_exist_ok=False) -> str:
        output = await self.run_command(f"cat {path}")
        if "No such file" in output and does_not_exist_ok:
            return ""
        return output

    async def write_file(self, path: str, content: str):
        encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        cmd = f'echo "{encoded}" | base64 -d > {path}'
        await self.run_command(cmd)

    async def commit_changes(self, commit_message: str):
        await self.run_command("git add -A")
        await self.run_command(f"git commit -m {commit_message}")

    async def stream_file_contents(self, path: str, binary_mode=False) -> AsyncGenerator[Union[str, bytes], None]:
        content = await self.read_file_contents(path)
        if binary_mode:
            yield content.encode("utf-8")
        else:
            yield content

    async def terminate(self):
        """
        Stop + remove the container
        """
        if self.container:
            try:
                self.container.stop()
                self.container.remove(force=True)
            except:
                pass
        self.container = None

        # Clear from DB
        db_sess = next(get_db())
        self.service.docker_container_id = None
        db_sess.commit()
    
    @classmethod
    async def terminate_project_containers(cls, project: Project):
        """
        For example, each 'service' might store a docker_container_id.
        We can remove them here.
        """
        client = docker.from_env()
        # If single container, maybe project.docker_container_id
        # If multiple services, iterate over project.services
        for svc in project.services:
            if svc.docker_container_id:
                try:
                    container = client.containers.get(svc.docker_container_id)
                    container.stop()
                    container.remove(force=True)
                    svc.docker_container_id = None
                except:
                    pass