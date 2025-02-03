# backend/routers/project_socket.py

from fastapi import APIRouter, WebSocket, WebSocketException, WebSocketDisconnect
from typing import Dict, List, Optional, Tuple
from enum import Enum
from asyncio import create_task, Lock
from pydantic import BaseModel
import datetime
import asyncio
import traceback

# UPDATED imports to reference the new abstract + helpers
from sandbox.sandbox import (
    BaseSandbox,
    SandboxNotReadyException,
)
from sandbox.local_docker_sandbox import LocalDockerSandbox
from sandbox.sandbox_handler import get_sandbox_for_project
from agents.agent import Agent, ChatMessage
from agents.diff import DiffApplier
from db.database import get_db
from db.models import Project, Message as DbChatMessage, Stack, User, Chat, Service, ServiceType
from db.queries import get_chat_for_user
from agents.prompts import write_commit_message
from routers.auth import get_current_user_from_token
from sqlalchemy.orm import Session

class SandboxStatus(str, Enum):
    OFFLINE = "OFFLINE"
    BUILDING = "BUILDING"
    BUILDING_WAITING = "BUILDING_WAITING"
    READY = "READY"
    WORKING = "WORKING"
    WORKING_APPLYING = "WORKING_APPLYING"

class ProjectStatusResponse(BaseModel):
    for_type: str = "status"
    project_id: int
    sandbox_statuses: Dict[int, SandboxStatus]
    tunnels: Dict[int, str]
    backend_file_paths: Optional[List[str]] = None
    frontend_file_paths: Optional[List[str]] = None
    git_log: Optional[str] = None
    frontend_tunnel: Optional[str] = None


class ChatUpdateResponse(BaseModel):
    for_type: str = "chat_update"
    chat_id: int
    message: ChatMessage
    follow_ups: Optional[List[str]] = None
    navigate_to: Optional[str] = None

class ChatChunkResponse(BaseModel):
    for_type: str = "chat_chunk"
    role: str
    content: str
    thinking_content: str

def _message_to_db_message(message: ChatMessage, chat_id: int) -> DbChatMessage:
    return DbChatMessage(
        role=message.role,
        content=message.content,
        images=message.images,
        chat_id=chat_id,
    )

def _db_message_to_message(db_message: DbChatMessage) -> ChatMessage:
    return ChatMessage(
        id=db_message.id,
        role=db_message.role,
        content=db_message.content,
        images=db_message.images,
    )

router = APIRouter(tags=["websockets"])

async def _apply_and_lint_and_commit(diff_applier: DiffApplier, sandbox: BaseSandbox):
    """
    Called after we collect all partial diffs from the agent and finalize them.
    We do 'npm run lint', apply ESLint fixes, and commit.
    """
    _, has_lint_file = await asyncio.gather(
        diff_applier.apply(),
        sandbox.has_file("/app/frontend/.eslintrc.json"),
    )
    if has_lint_file:
        lint_output = await sandbox.run_command(
            "npm run lint", workdir="/app/frontend"
        )
        print(lint_output)
        if "Error:" in lint_output:
            await diff_applier.apply_eslint(lint_output)

    commit_msg = await write_commit_message(diff_applier.total_content)
    await sandbox.commit_changes(commit_msg)

class ProjectManager:
    """
    Manages a single project's WebSocket connections, agents, and multiple sandbox instances.
    Each service within the project has its own sandbox.
    """

    def __init__(self, db: Session, project_id: int):
        self.db = db
        self.project_id = project_id
        self.chat_sockets: Dict[int, List[WebSocket]] = {}
        self.chat_agents: Dict[int, Agent] = {}
        self.chat_users: Dict[int, User] = {}
        self.lock: Lock = Lock()

        # Mapping from service_id to SandboxStatus
        self.sandbox_statuses: Dict[int, SandboxStatus] = {}
        # Mapping from service_id to BaseSandbox
        self.sandboxes: Dict[int, BaseSandbox] = {}

        self.tunnels: Dict[int, str] = {}
        self.backend_file_paths: Optional[List[str]] = None
        self.frontend_file_paths: Optional[List[str]] = None
        self.git_log: Optional[str] = None
        
        self.frontend_tunnel: Optional[str] = None

        self.last_activity = datetime.datetime.now()

    def is_inactive(self, timeout_minutes: int = 30) -> bool:
        """
        If no active sockets and it's been > 'timeout_minutes' since last activity, we consider it inactive.
        """
        if len(self.chat_sockets) == 0:
            delta = datetime.datetime.now() - self.last_activity
            return delta > datetime.timedelta(minutes=timeout_minutes)
        return False

    async def kill(self):
        """
        Forcefully close all websockets, kill all sandbox resources, etc.
        """
        for service_id, sandbox in self.sandboxes.items():
            self.sandbox_statuses[service_id] = SandboxStatus.BUILDING
            await self.emit_project(await self._get_project_status())

            if isinstance(sandbox, LocalDockerSandbox):
                await sandbox.terminate()

        # Close websockets
        close_tasks = []
        for sockets in self.chat_sockets.values():
            for socket in sockets:
                try:
                    close_tasks.append(socket.close())
                except Exception:
                    pass
        if close_tasks:
            await asyncio.gather(*close_tasks)

        # Clear references
        self.chat_sockets.clear()
        self.chat_agents.clear()
        self.chat_users.clear()
        self.sandboxes.clear()
        self.sandbox_statuses.clear()

    def start(self):
        """
        Kick off the background task that tries to manage the sandbox creation + readiness.
        """
        create_task(self._try_manage_sandboxes())

    async def _try_manage_sandboxes(self):
        """
        Repeatedly attempt to get+start the sandboxes for this project until success or error.
        """
        project = self.db.query(Project).filter(Project.id == self.project_id).first()
        if not project:
            print(f"Project {self.project_id} not found, aborting sandbox management.")
            return

        services = project.services
        for service in services:
            self.sandbox_statuses[service.id] = SandboxStatus.BUILDING
            await self.emit_project(await self._get_project_status())

            create_task(self._manage_sandbox(service))

    async def _manage_sandbox(self, service: Service):
        """
        Create or get the sandbox for a specific service.
        """
        try:
            # Pass the already loaded project instance
            project = self.db.query(Project).filter(Project.id == self.project_id).first()
            if not project:
                print(f"Project {self.project_id} not found, aborting sandbox management.")
                return
            print("_manage_sandbox : ", service.service_type)
            sandbox = (await get_sandbox_for_project(project=project, create_if_missing=True, service_id=service.id))[0]
            print("got sandbox : ", sandbox)

            self.sandboxes[service.id] = sandbox
            self.sandbox_statuses[service.id] = SandboxStatus.READY
            
            # Read file paths and git log if backend service
            if service.service_type == ServiceType.BACKEND:
                self.backend_file_paths = await sandbox.get_file_paths()
                self.git_log = await sandbox.read_file_contents("/app/git.log", does_not_exist_ok=True)
            elif service.service_type == ServiceType.FRONTEND:
                self.frontend_file_paths = await sandbox.get_file_paths()
                self.tunnels[service.id] = sandbox.service.preview_url
                self.frontend_tunnel = sandbox.service.preview_url
                
                
            print("emit  : ", await self._get_project_status())
            await self.emit_project(await self._get_project_status())

            # Assign sandbox to existing Agents
            for agent in self.chat_agents.values():
                agent.set_sandbox(sandbox)

        except SandboxNotReadyException:
            self.sandbox_statuses[service.id] = SandboxStatus.BUILDING_WAITING
            await self.emit_project(await self._get_project_status())
            await asyncio.sleep(10)
            create_task(self._manage_sandbox(service))
        except Exception as e:
            print(f"Error managing sandbox for service {service.id}: {e}\n{traceback.format_exc()}")
            self.sandbox_statuses[service.id] = SandboxStatus.OFFLINE
            await self.emit_project(await self._get_project_status())
            await asyncio.sleep(30)
            create_task(self._manage_sandbox(service))

    async def _get_project_status(self) -> ProjectStatusResponse:
        return ProjectStatusResponse(
            project_id=self.project_id,
            sandbox_statuses=self.sandbox_statuses.copy(),
            tunnels=self.tunnels,
            backend_file_paths=self.backend_file_paths,
            frontend_file_paths=self.frontend_file_paths,
            git_log=self.git_log,
            frontend_tunnel=self.frontend_tunnel,
        )


    async def add_chat_socket(self, chat_id: int, websocket: WebSocket):
        self.last_activity = datetime.datetime.now()
        if chat_id not in self.chat_sockets:
            project = self.db.query(Project).filter(Project.id == self.project_id).first()
            if not project:
                await websocket.close()
                return

            # Assuming chats interact with the backend service
            backend_service = next(
                (svc for svc in project.services if svc.service_type == ServiceType.BACKEND),
                None
            )
            if not backend_service:
                await websocket.close(code=1008, reason="Backend service not found.")
                return

            agent = Agent(project, backend_service.stack, self.db.query(User).filter(User.id == project.user_id).first())
            sandbox = self.sandboxes.get(backend_service.id)
            agent.set_sandbox(sandbox)
            self.chat_agents[chat_id] = agent
            self.chat_sockets[chat_id] = []
            self.chat_users[chat_id] = agent.user

        self.chat_sockets[chat_id].append(websocket)
        await self.emit_project(await self._get_project_status())

    def remove_chat_socket(self, chat_id: int, websocket: WebSocket):
        try:
            self.chat_sockets[chat_id].remove(websocket)
        except ValueError:
            pass
        if len(self.chat_sockets[chat_id]) == 0:
            del self.chat_sockets[chat_id]
            del self.chat_agents[chat_id]
            del self.chat_users[chat_id]

    async def on_chat_message(self, chat_id: int, message: ChatMessage):
        self.last_activity = datetime.datetime.now()
        async with self.lock:
            await self._handle_chat_message(chat_id, message)

    async def _handle_chat_message(self, chat_id: int, message: ChatMessage):
        """
        Actually handle the user's chat message: store to DB, run the agent, produce diffs, etc.
        """
        # Assuming interaction is with the backend sandbox
        project = self.db.query(Project).filter(Project.id == self.project_id).first()
        backend_service = next(
            (svc for svc in project.services if svc.service_type == ServiceType.BACKEND),
            None
        )
        if not backend_service:
            await self.emit_chat(chat_id, {"error": "Backend service not found."})
            return

        sandbox = self.sandboxes.get(backend_service.id)
        if not sandbox or getattr(sandbox, 'ready', False) is False:
            self.sandbox_statuses[backend_service.id] = SandboxStatus.OFFLINE
            await self.emit_project(await self._get_project_status())
            await self.emit_chat(chat_id, {"error": "Backend sandbox is not running."})
            return

        self.sandbox_statuses[backend_service.id] = SandboxStatus.WORKING
        await self.emit_project(await self._get_project_status())

        # 1) Save user message
        db_msg = _message_to_db_message(message, chat_id)
        self.db.add(db_msg)
        self.db.commit()
        self.db.refresh(db_msg)

        # 2) Emit user message update
        await self.emit_chat(
            chat_id,
            ChatUpdateResponse(
                chat_id=chat_id,
                message=_db_message_to_message(db_msg)
            ),
        )

        # 3) Run agent logic
        agent = self.chat_agents[chat_id]
        db_messages = (
            self.db.query(DbChatMessage)
            .filter(DbChatMessage.chat_id == chat_id)
            .order_by(DbChatMessage.created_at)
            .all()
        )
        all_messages = [_db_message_to_message(m) for m in db_messages]

        total_content = ""
        diff_applier = DiffApplier(agent.sandbox)

        async for partial_chunk in agent.step(
            all_messages,
            self.backend_file_paths,  # send backend file paths
            self.git_log
        ):
            # Collect partial text
            total_content += partial_chunk.delta_content
            # Also feed diff
            diff_applier.ingest(partial_chunk.delta_content)

            await self.emit_chat(
                chat_id,
                ChatChunkResponse(
                    role="assistant",
                    content=partial_chunk.delta_content,
                    thinking_content=partial_chunk.delta_thinking_content
                ),
            )

        # 4) Save the final assistant message
        assistant_msg = ChatMessage(role="assistant", content=total_content)
        db_assistant_msg = _message_to_db_message(assistant_msg, chat_id)

        project = self.db.query(Project).filter(Project.id == self.project_id).first()
        project.modal_sandbox_last_used_at = datetime.datetime.now()

        self.db.add(db_assistant_msg)
        self.db.commit()

        # 5) Now apply final diffs + lint + commit
        self.sandbox_statuses[backend_service.id] = SandboxStatus.WORKING_APPLYING
        await self.emit_project(await self._get_project_status())
        await diff_applier.apply()
        
        commit_msg = await write_commit_message(total_content)
        await agent.sandbox.commit_changes(commit_msg)
        
        for svc in project.services:
            if svc.service_type == ServiceType.FRONTEND and svc.id in self.sandboxes:
                frontend_sandbox = self.sandboxes[svc.id]
                frontend_diff_applier = DiffApplier(frontend_sandbox)
                frontend_diff_applier.ingest(total_content)
                await frontend_diff_applier.apply()
                self.sandbox_statuses[svc.id] = SandboxStatus.READY
                # (7) Refresh file trees from both services
        if backend_service.id in self.sandboxes:
            self.backend_file_paths = await self.sandboxes[backend_service.id].get_file_paths()
        for svc in project.services:
            if svc.service_type == ServiceType.FRONTEND and svc.id in self.sandboxes:
                self.frontend_file_paths = await self.sandboxes[svc.id].get_file_paths()

        await self.emit_project(await self._get_project_status())

        await self.emit_chat(
            chat_id,
            ChatUpdateResponse(
                chat_id=chat_id,
                message=_db_message_to_message(db_assistant_msg),
                follow_ups=await agent.suggest_follow_ups(all_messages + [assistant_msg]),
                navigate_to=agent.working_page,
            ),
        )        
        # Do lint + commit
        # follow_ups = None
        # try:
        #     await _apply_and_lint_and_commit(diff_applier, sandbox)
        #     # Get follow ups
        #     follow_ups = await agent.suggest_follow_ups(all_messages + [assistant_msg])
        # except Exception as e:
        #     print("Error applying diffs or follow ups:", e)

        # # 6) Emit final chat update
        # await self.emit_chat(
        #     chat_id,
        #     ChatUpdateResponse(
        #         chat_id=chat_id,
        #         message=_db_message_to_message(db_assistant_msg),
        #         follow_ups=follow_ups,
        #         navigate_to=agent.working_page,
        #     ),
        # )

        # 7) Reset status to READY
        self.sandbox_statuses[backend_service.id] = SandboxStatus.READY
        # Re-pull file paths + git log
        self.file_paths = await sandbox.get_file_paths()
        self.git_log = await sandbox.read_file_contents("/app/git.log", does_not_exist_ok=True)
        await self.emit_project(await self._get_project_status())

    async def emit_project(self, data: ProjectStatusResponse):
        """
        Broadcast a status update to all chat sockets for this project.
        """
        await asyncio.gather(
            *[self.emit_chat(cid, data) for cid in self.chat_sockets]
        )

    async def emit_chat(self, chat_id: int, data: BaseModel):
        """
        Broadcast 'data' to the specific chat room's sockets as JSON.
        """
        if chat_id not in self.chat_sockets:
            return
        sockets = list(self.chat_sockets[chat_id])

        async def _try_send(sock: WebSocket):
            try:
                await sock.send_json(data.model_dump())
            except Exception:
                try:
                    self.chat_sockets[chat_id].remove(sock)
                except ValueError:
                    pass

        await asyncio.gather(*[_try_send(s) for s in sockets])

# We keep a global dictionary of project managers
project_managers: Dict[int, ProjectManager] = {}

@router.websocket("/api/ws/chat/{chat_id}")
async def websocket_endpoint(websocket: WebSocket, chat_id: int):
    """
    The main WebSocket endpoint.
    1) Auth user from query param token
    2) Get project from chat
    3) Launch or find the ProjectManager
    4) Listen for user messages
    """
    db = next(get_db())
    token = websocket.query_params.get("token")
    current_user = await get_current_user_from_token(token, db)

    # Check chat + project
    chat = get_chat_for_user(db, chat_id, current_user)
    if not chat:
        await websocket.close(code=1008, reason="Chat not found.")
        return

    project = chat.project
    if not project:
        await websocket.close(code=1008, reason="Project not found.")
        return

    # Find or create manager
    if project.id not in project_managers:
        pm = ProjectManager(db, project.id)
        pm.start()
        project_managers[project.id] = pm
    else:
        pm = project_managers[project.id]

    # Accept & register socket
    await websocket.accept()
    await pm.add_chat_socket(chat_id, websocket)

    try:
        # Read new user messages
        while True:
            raw_data = await websocket.receive_text()
            data = ChatMessage.model_validate_json(raw_data)
            # Schedule the agent to handle the message
            create_task(pm.on_chat_message(chat_id, data))

    except WebSocketDisconnect:
        pass
    except RuntimeError as e:
        if "WebSocket is not connected" in str(e):
            pass
        else:
            print("WebSocket runtime error:", e, traceback.format_exc())
    except Exception as e:
        print("WebSocket endpoint error:", e, traceback.format_exc())
    finally:
        pm.remove_chat_socket(chat_id, websocket)
        try:
            await websocket.close()
        except Exception:
            pass
        db.close()
