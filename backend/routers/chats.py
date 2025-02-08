from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List
import secrets
from datetime import datetime, timezone

from sandbox.local_docker_sandbox import LocalDockerSandbox
from db.database import get_db
from db.models import (
    Service,
    ServiceType,
    User,
    Chat,
    Team,
    Project,
    Stack,
    CreditDailyPool,
    TeamCreditPurchase,
)
from db.queries import get_chat_for_user
from agents.prompts import name_chat, pick_stack
from sandbox.sandbox import BaseSandbox  # Abstract sandbox
from config import (
    CREDITS_CHAT_COST,
    CREDIT_MAX_CHATS_FOR_SHARED_POOL,
    PROJECTS_SET_NEVER_CLEANUP,
    CREDITS_DAILY_SHARED_POOL,
)
from schemas.models import ChatCreate, ChatUpdate, ChatResponse, PreviewUrlResponse
from routers.auth import get_current_user_from_token

router = APIRouter(prefix="/api/chats", tags=["chats"])


@router.get("", response_model=List[ChatResponse])
async def get_user_chats(
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
):
    return (
        db.query(Chat)
        .filter(Chat.user_id == current_user.id)
        .options(joinedload(Chat.messages), joinedload(Chat.project))
        .all()
    )


@router.get("/{chat_id}", response_model=ChatResponse)
async def get_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
):
    chat = (
        db.query(Chat)
        .filter(Chat.id == chat_id, Chat.user_id == current_user.id)
        .options(joinedload(Chat.messages), joinedload(Chat.project))
        .first()
    )
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    if chat.messages:
        chat.messages = sorted(chat.messages, key=lambda x: x.created_at)
    return chat


async def _pick_stack(db: Session, seed_prompt: str):
    """
    Picks two stacks (frontend and backend) based on the seed_prompt.
    Returns the corresponding Stack objects from the database.
    
    Args:
        db (Session): The database session.
        seed_prompt (str): The initial prompt describing the project.
        
    Returns:
        Tuple[Stack, Stack]: A tuple containing the frontend and backend Stack objects.
    """
    # Retrieve all stack titles from the database
    stack_titles = [s.title for s in db.query(Stack).all()]
    
    # Define a default stack
    default_stack = ["Next.js Shadcn", "FastAPI"]
    
    # Use pick_stack to determine frontend and backend stacks
    frontend_title, backend_title = await pick_stack(seed_prompt, stack_titles, default=default_stack)
    
    # Fetch the corresponding Stack objects from the database
    frontend_stack = db.query(Stack).filter(Stack.title == frontend_title).first()
    backend_stack = db.query(Stack).filter(Stack.title == backend_title).first()
    
    # If either stack is not found, use the default stack
    if not frontend_stack:
        frontend_stack = db.query(Stack).filter(Stack.title == default_stack).first()
    if not backend_stack:
        backend_stack = db.query(Stack).filter(Stack.title == default_stack).first()
    
    return (frontend_stack, backend_stack)


async def _check_and_deduct_credits(
    db: Session, team: Team, cost: int, user: User
) -> None:
    """
    Check if team has enough credits and deduct them, falling back to shared pool if needed.
    Raises HTTPException if not enough credits available.
    """
    if team.credits < cost:
        # Check if team has ever purchased credits
        has_purchased = (
            db.query(TeamCreditPurchase)
            .filter(TeamCreditPurchase.team_id == team.id)
            .first()
            is not None
        )

        # Check user's total chat count
        total_chats = db.query(Chat).filter(Chat.user_id == user.id).count()

        # Only allow the daily shared pool if never purchased and under max chat limit
        if has_purchased or total_chats >= CREDIT_MAX_CHATS_FOR_SHARED_POOL:
            raise HTTPException(
                status_code=402,
                detail=f"Not enough credits. Team has {team.credits} credits. "
                f"Required: {cost}. Purchase more credits to continue.",
            )

        today = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        daily_pool = (
            db.query(CreditDailyPool).filter(CreditDailyPool.date == today).first()
        )

        if not daily_pool:
            daily_pool = CreditDailyPool(
                date=today, credits_remaining=CREDITS_DAILY_SHARED_POOL
            )
            db.add(daily_pool)
            db.commit()
            db.refresh(daily_pool)

        if daily_pool.credits_remaining < cost:
            raise HTTPException(
                status_code=402,
                detail=f"Not enough credits. Team has {team.credits} credits and "
                f"daily pool has {daily_pool.credits_remaining} credits. Required: {cost}",
            )

        daily_pool.credits_remaining -= cost
    else:
        team.credits -= cost


@router.post("", response_model=ChatResponse)
async def create_chat(
    chat: ChatCreate,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
):
    """
    Create a new Chat. If project_id is None, create a new project with selected stacks.
    Otherwise, reuse the existing project.
    """
    team = (
        db.query(Team)
        .filter(Team.id == chat.team_id, Team.members.any(user_id=current_user.id))
        .first()
    )
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Pick frontend and backend stacks based on seed_prompt
    frontend_stack, backend_stack = await _pick_stack(db, chat.seed_prompt)

    # Generate project/chat names from seed_prompt
    project_name, project_description, chat_name = await name_chat(chat.seed_prompt)

    # If no project provided, create a new one
    if chat.project_id is None:
        project = Project(
            name=project_name,
            description=project_description,
            custom_instructions="",
            user_id=current_user.id,
            team_id=team.id,
            stack_id=backend_stack.id,
            modal_never_cleanup=PROJECTS_SET_NEVER_CLEANUP,
        )
        db.add(project)
        db.flush()  # So we get project.id for the Services

        # Create two services: frontend and backend
        fe_service = Service(
            project_id=project.id, stack_id=frontend_stack.id, service_type=ServiceType.FRONTEND
        )
        be_service = Service(
            project_id=project.id, stack_id=backend_stack.id, service_type=ServiceType.BACKEND
        )
        db.add(fe_service)
        db.add(be_service)
        db.commit()
        db.refresh(project)
    else:
        # Reuse existing project
        project = (
            db.query(Project)
            .filter(
                Project.id == chat.project_id,
                (Project.user_id == current_user.id) | (Project.team_id == team.id),
            )
            .first()
        )
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

    # Now create the chat
    new_chat = Chat(
        name=chat_name,
        project_id=project.id,
        user_id=current_user.id,
        
    )
    db.add(new_chat)
    db.commit()
    db.refresh(new_chat)
    return new_chat

@router.delete("/{chat_id}")
async def delete_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
):
    chat = get_chat_for_user(db, chat_id, current_user)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")

    project_id = chat.project_id
    db.delete(chat)

    # If no other chats remain in that project, we delete the project
    remaining_chats = (
        db.query(Chat)
        .filter(Chat.project_id == project_id, Chat.id != chat_id)
        .first()
    )
    project_deleted = None
    if not remaining_chats:
        project_deleted = db.query(Project).filter(Project.id == project_id).first()
        if project_deleted:
            db.delete(project_deleted)

    db.commit()

    if project_deleted:
        # Clean up its sandbox
        await BaseSandbox.destroy_project_resources(project_deleted)

    return {"message": "Chat deleted successfully"}


@router.patch("/{chat_id}", response_model=ChatResponse)
async def update_chat(
    chat_id: int,
    chat_update: ChatUpdate,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
):
    chat = get_chat_for_user(db, chat_id, current_user)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")

    for field, value in chat_update.dict(exclude_unset=True).items():
        setattr(chat, field, value)

    try:
        db.commit()
        db.refresh(chat)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return chat


@router.get("/public/{share_id}", response_model=ChatResponse)
async def get_public_chat(
    share_id: str,
    db: Session = Depends(get_db),
):
    chat = (
        db.query(Chat)
        .filter(Chat.public_share_id == share_id, Chat.is_public)
        .options(joinedload(Chat.messages), joinedload(Chat.project))
        .first()
    )
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    if chat.messages:
        chat.messages = sorted(chat.messages, key=lambda x: x.created_at)
    return chat


@router.post("/{chat_id}/share", response_model=ChatResponse)
async def share_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
):
    chat = get_chat_for_user(db, chat_id, current_user)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")

    if not chat.is_public:
        chat.is_public = True
        if not chat.public_share_id:
            chat.public_share_id = secrets.token_urlsafe(16)
        db.commit()
        db.refresh(chat)

    return chat


@router.post("/{chat_id}/unshare", response_model=ChatResponse)
async def unshare_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
):
    chat = get_chat_for_user(db, chat_id, current_user)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")

    chat.is_public = False
    db.commit()
    db.refresh(chat)

    return chat


@router.get("/public/{share_id}/preview-url", response_model=PreviewUrlResponse)
async def get_public_chat_preview_url(share_id: str, db: Session = Depends(get_db)):
    """
    Return the *frontend* sandbox's preview URL for a public chat.
    """
    chat = (
        db.query(Chat)
        .filter(Chat.public_share_id == share_id, Chat.is_public.is_(True))
        .options(joinedload(Chat.project))
        .first()
    )
    if not chat or not chat.project:
        raise HTTPException(status_code=404, detail="Chat or project not found")

    # find the frontend service
    fe_svc = (
        db.query(Service)
        .filter(Service.project_id == chat.project_id, Service.service_type == ServiceType.FRONTEND)
        .first()
    )
    if not fe_svc:
        raise HTTPException(status_code=404, detail="No frontend service found in project")


    # get or create the sandbox for that service
    sandbox = await BaseSandbox.get_or_create(service_id=fe_svc.id, create_if_missing=True)

    if sandbox.isinstance(LocalDockerSandbox):
        return {"preview_url": sandbox.preview_url}
    else:
        await sandbox.wait_for_up()
        tunnels = await sandbox.sb.tunnels.aio()
        if not tunnels:
            raise HTTPException(status_code=500, detail="No tunnels available yet")

        # pick port 3000 if it exists, else the first
        port = 3000 if 3000 in tunnels else next(iter(tunnels.keys()))
        return {"preview_url": tunnels[port].url}