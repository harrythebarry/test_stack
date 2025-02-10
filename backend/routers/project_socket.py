import json
import uuid
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
from graphAgent.app import agent_orchestrator
from routers.auth import get_current_user_from_token
from sqlalchemy.orm import Session
 
class SandboxStatus(str, Enum):
    OFFLINE = "OFFLINE"
    BUILDING = "BUILDING"
    BUILDING_WAITING = "BUILDING_WAITING"
    READY = "READY"
    WORKING = "WORKING"
    WORKING_APPLYING = "WORKING_APPLYING"
    
    

class ResponseFormat(BaseModel):
    file_path: str
    content: str
    
class LLMResponseFormat(BaseModel):
    response_format: ResponseFormat
 
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
    print("Starting lint and commit process.")
    _, has_lint_file = await asyncio.gather(
        diff_applier.apply(),
        sandbox.has_file("/app/frontend/.eslintrc.json"),
    )
    if has_lint_file:
        print("Lint file detected, running 'npm run lint' command.")
        lint_output = await sandbox.run_command(
            "npm run lint", workdir="/app/frontend"
        )
        print(f"Lint output: {lint_output}")
        if "Error:" in lint_output:
            print("Lint errors detected, applying ESLint fixes.")
            await diff_applier.apply_eslint(lint_output)
 
    commit_msg = await write_commit_message(diff_applier.total_content)
    print(f"Commit message generated: {commit_msg}")
    await sandbox.commit_changes(commit_msg)
 
class ProjectManager:
    """
    Manages a single project's WebSocket connections, agents, and multiple sandbox instances.
    Each service within the project has its own sandbox.
    """
 
    def __init__(self, db: Session, project_id: int):
        print(f"Initializing ProjectManager for project {project_id}")
        self.db = db
        self.project_id = project_id
        self.chat_sockets: Dict[int, List[WebSocket]] = {}
        self.chat_agents: Dict[int, Dict[str, Agent]] = {}
        self.chat_users: Dict[int, User] = {}
        self.lock: Lock = Lock()
 
        # Mapping from service_id to SandboxStatus
        self.sandbox_statuses: Dict[int, SandboxStatus] = {}
        # Mapping from service_id to BaseSandbox
        self.sandboxes: Dict[int, LocalDockerSandbox] = {}
 
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
            print(f"Checking inactivity: {delta.total_seconds()} seconds since last activity.")
            return delta > datetime.timedelta(minutes=timeout_minutes)
        return False
 
    async def kill(self):
        """
        Forcefully close all websockets, kill all sandbox resources, etc.
        """
        print("Killing all resources and closing websockets.")
        for service_id, sandbox in self.sandboxes.items():
            print(f"Terminating sandbox for service {service_id}.")
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
                    print("Closing websocket.")
                except Exception:
                    print("Error closing websocket.")
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
        print(f"Starting sandbox management for project {self.project_id}.")
        create_task(self._try_manage_sandboxes())
 
    async def _try_manage_sandboxes(self):
        """
        Repeatedly attempt to get+start the sandboxes for this project until success or error.
        """
        print(f"Managing sandboxes for project {self.project_id}.")
        project = self.db.query(Project).filter(Project.id == self.project_id).first()
        if not project:
            print(f"Project {self.project_id} not found, aborting sandbox management.")
            return
 
        services = project.services
        for service in services:
            print(f"Starting sandbox creation for service {service.id}.")
            self.sandbox_statuses[service.id] = SandboxStatus.BUILDING
            print("try manage sandboxes emit project")
            await self.emit_project(await self._get_project_status())
 
            create_task(self._manage_sandbox(service))
 
    async def _manage_sandbox(self, service: Service):
        """
        Create or get the sandbox for a specific service.
        """
        try:
            print(f"Managing sandbox for service {service.id} of type {service.service_type}.")
            project = self.db.query(Project).filter(Project.id == self.project_id).first()
            if not project:
                print(f"Project {self.project_id} not found, aborting sandbox management.")
                return
 
            sandbox = (await get_sandbox_for_project(project=project, create_if_missing=True, service_id=service.id))[0]
            print(f"Got sandbox for service {service.id}: {sandbox}")
 
            self.sandboxes[service.id] = sandbox
            self.sandbox_statuses[service.id] = SandboxStatus.READY
            print(f"Sandbox for service {service.id} is now READY.")
 
            # Read file paths and git log if backend service
            if service.service_type == ServiceType.BACKEND:
                print(f"Reading file paths and git log for backend service {service.id}.")
                self.backend_file_paths = await sandbox.get_file_paths()
                self.git_log = await sandbox.read_file_contents("/app/git.log", does_not_exist_ok=True)
            elif service.service_type == ServiceType.FRONTEND:
                print(f"Reading file paths for frontend service {service.id}.")
                self.frontend_file_paths = await sandbox.get_file_paths()
                self.tunnels[service.id] = sandbox.service.preview_url
                self.frontend_tunnel = sandbox.service.preview_url
 
            await self.emit_project(await self._get_project_status())
      
                
 
        except SandboxNotReadyException:
            print(f"Sandbox for service {service.id} is not ready, retrying.")
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
        print(f"Retrieving project status for project {self.project_id}.")
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
        print(f"Adding websocket for chat {chat_id}.")
        self.last_activity = datetime.datetime.now()
        if chat_id not in self.chat_sockets:
            project = self.db.query(Project).filter(Project.id == self.project_id).first()
            if not project:
                print(f"Project {self.project_id} not found, closing websocket.")
                await websocket.close()
                return
 
            # Find both frontend and backend services
            frontend_service = next(
                (svc for svc in project.services if svc.service_type == ServiceType.FRONTEND),
                None
            )
            backend_service = next(
                (svc for svc in project.services if svc.service_type == ServiceType.BACKEND),
                None
            )
 
            if not frontend_service or not backend_service:
                print(f"Services for frontend or backend not found for project {self.project_id}, closing websocket.")
                await websocket.close(code=1008, reason="Frontend or backend service not found.")
                return
 
            # Create agents for both frontend and backend
            frontend_agent = Agent(project, frontend_service.stack, self.db.query(User).filter(User.id == project.user_id).first())
            backend_agent = Agent(project, backend_service.stack, self.db.query(User).filter(User.id == project.user_id).first())
 
            # Assign sandboxes for both frontend and backend
            frontend_sandbox = self.sandboxes.get(frontend_service.id)
            backend_sandbox = self.sandboxes.get(backend_service.id)
 
            # Set sandboxes for both agents
            frontend_agent.set_sandbox(frontend_sandbox)
            backend_agent.set_sandbox(backend_sandbox)
 
            # Store agents and websockets
            self.chat_agents[chat_id] = {'frontend': frontend_agent, 'backend': backend_agent}
            self.chat_sockets[chat_id] = []
            self.chat_users[chat_id] = {'frontend': frontend_agent.user, 'backend': backend_agent.user}
 
        self.chat_sockets[chat_id].append(websocket)
        print("add_chat_socket emit project")
        await self.emit_project(await self._get_project_status())
 
    def remove_chat_socket(self, chat_id: int, websocket: WebSocket):
        print(f"Removing websocket for chat {chat_id}.")
        try:
            self.chat_sockets[chat_id].remove(websocket)
        except ValueError:
            pass
        if len(self.chat_sockets[chat_id]) == 0:
            print(f"All websockets removed for chat {chat_id}. Clearing data.")
            del self.chat_sockets[chat_id]
            del self.chat_agents[chat_id] 
            del self.chat_users[chat_id]
 
    async def on_chat_message(self,project: Project, chat_id: int, message: ChatMessage):
        print(f"Received message from chat {chat_id}: {message.content}.")
        self.last_activity = datetime.datetime.now()
        async with self.lock:
            await self._handle_chat_message(project, chat_id, message)
 
    async def _handle_chat_message(self, project: Project, chat_id: int, message: ChatMessage):
        """
        Actually handle the user's chat message: store to DB, run the agent, produce diffs, etc.
        """
        print(f"Handling chat message for chat {chat_id}.")
        # Assuming interaction is with the backend sandbox
        project = self.db.query(Project).filter(Project.id == self.project_id).first()
        backend_service = next(
            (svc for svc in project.services if svc.service_type == ServiceType.BACKEND),
            None
        )
        frontend_service = next(
            (svc for svc in project.services if svc.service_type == ServiceType.FRONTEND),
            None
        )
 
        if not backend_service and not frontend_service:
            print(f"Neither Backend nor Frontend service found for project {self.project_id}.")
            await self.emit_chat(chat_id, {"error": "Neither Backend nor Frontend service found."})
            return
 
        #TODO : define two services for frontend and backend
        # Get the sandbox for the identified service
        backend_sandbox = self.sandboxes.get(backend_service.id)
        frontend_sandbox = self.sandboxes.get(frontend_service.id)
        
        #TODO : check the existence of the sandbox for both frontend and backend
        
        if not backend_sandbox or getattr(backend_sandbox, 'ready', False) is False:
            print(f"Sandbox for service {backend_service.id} is not running, emitting error.")
            self.sandbox_statuses[backend_service.id] = SandboxStatus.OFFLINE
            await self.emit_project(await self._get_project_status())
            await self.emit_chat(chat_id, {"error": f"{backend_service.service_type.value} sandbox is not running."})
            return
        
        if not frontend_sandbox or getattr(frontend_sandbox, 'ready', False) is False:
            print(f"Sandbox for service {frontend_service.id} is not running, emitting error.")
            self.sandbox_statuses[frontend_service.id] = SandboxStatus.OFFLINE
            await self.emit_project(await self._get_project_status())
            await self.emit_chat(chat_id, {"error": f"{frontend_service.service_type.value} sandbox is not running."})
            return
        
        
        
        
        
 
        print(f"Sandbox for service {backend_service.id} is ready. Proceeding with message processing.")
        self.sandbox_statuses[backend_service.id] = SandboxStatus.WORKING
        
        print(f"Sandbox for service {frontend_service.id} is ready. Proceeding with message processing.")
        self.sandbox_statuses[frontend_service.id] = SandboxStatus.WORKING
        
        await self.emit_project(await self._get_project_status())
 
        # 1) Save user message
        db_msg = _message_to_db_message(message, chat_id)
        print(f"Saving user message for chat {chat_id}.")
        self.db.add(db_msg)
        self.db.commit()
        self.db.refresh(db_msg)
 
        # 2) Emit user message update
        print(f"Emitting user message update for chat {chat_id}.")
        await self.emit_chat(
            chat_id,
            ChatUpdateResponse(
                chat_id=chat_id,
                message=_db_message_to_message(db_msg)
            ),
        )
 
        # 3) Run agent logic
        print(f"Running agent logic for chat {chat_id}.")
        frontend_agent = self.chat_agents[chat_id]['frontend']
        backend_agent = self.chat_agents[chat_id]['backend']
        
        
        db_messages = (
            self.db.query(DbChatMessage)
            .filter(DbChatMessage.chat_id == chat_id)
            .order_by(DbChatMessage.created_at)
            .all()
        )
        all_messages = [_db_message_to_message(m) for m in db_messages]

        # completion call for backend agent

        thread=str(uuid.uuid4())
        be_port=backend_service.docker_port
        fe_port=frontend_service.docker_port
        
        total_content=agent_orchestrator(message.content,thread,be_port,fe_port)
        
            
        print("total_content",total_content)
        #TODO: THE total content is an array containing two objects, each with a 'response' key mapping to an array of file objects, where each file object has 'file_path' and 'file_content' keys. now each object should be convertered into a json string and then write into the docker container.
        llm_output_str_backend = json.dumps(total_content[0])
        llm_output_str_frontend = json.dumps(total_content[1])
        
        # Convert the total_content (a list of responses) to a JSON string.
        # Call the asynchronous method to write the files into the Docker container.
        print("writing files for backend")
        await backend_sandbox.write_files_from_llm_output(llm_output_str_backend)
        print("writing files for frontend")
        await frontend_sandbox.write_files_from_llm_output(llm_output_str_frontend)
        print("writing files finished")
        

        # print("running command for frontend")
        # await frontend_sandbox.run_command("npm run dev")
        # print("command running finished")
            
        #TODO : assistant message should be sent to both frontend and backend
        assistant_msg = ChatMessage(role="assistant", content="response from backend and frontend")
        db_assistant_msg = _message_to_db_message(assistant_msg, chat_id)
 
        print(f"Saving assistant message for chat {chat_id}.")
        self.db.add(db_assistant_msg)
        self.db.commit()
        self.db.refresh(db_assistant_msg)       
        

        #TODO : update the backend_file_paths and frontend_File_paths from teh sandbox container.         
        self.backend_file_paths = await backend_sandbox.get_file_paths()
        self.frontend_file_paths = await frontend_sandbox.get_file_paths()
        
                
 
        print(f"Finalizing project status for chat {chat_id}.")
        await self.emit_project(await self._get_project_status())
 
        await self.emit_chat(
            chat_id,
            ChatUpdateResponse(
                chat_id=chat_id,
                message=_db_message_to_message(db_assistant_msg),
                follow_ups=await frontend_agent.suggest_follow_ups(all_messages + [assistant_msg]),
                navigate_to=frontend_agent.working_page,
            ),
        )
        
        print(f"Resetting sandbox status to READY for service {backend_service.id}.")
        self.sandbox_statuses[backend_service.id] = SandboxStatus.READY
        print(f"Resetting sandbox status to READY for service {frontend_service.id}.")
        self.sandbox_statuses[frontend_service.id] = SandboxStatus.READY
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
        print("i came here")
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

            create_task(pm.on_chat_message(pm, chat_id, data))
#  
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
        print("chat socket is removed ")
        pm.remove_chat_socket(chat_id, websocket)
        try:
            await websocket.close()
        except Exception:
            pass
        db.close()
 
 