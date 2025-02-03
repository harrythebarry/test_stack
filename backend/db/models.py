"""
Updates:
$ alembic revision --autogenerate -m "..."
$ alembic upgrade head
"""

from sqlalchemy import (
    Column,
    String,
    Integer,
    ForeignKey,
    Text,
    DateTime,
    Enum,
    ARRAY,
    Boolean,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum as PyEnum

from .database import Base


class TimestampMixin:
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class UserType(PyEnum):
    WEB_DESIGNER = "web_designer"
    LEARNING_TO_CODE = "learning_to_code"
    EXPERT_DEVELOPER = "expert_developer"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    user_type = Column(Enum(UserType), nullable=False, default=UserType.WEB_DESIGNER)
    email = Column(String, unique=True, nullable=True)
    email_verified = Column(Boolean, nullable=False, default=False)
    projects = relationship(
        "Project", back_populates="owner", cascade="all, delete-orphan"
    )
    team_memberships = relationship(
        "TeamMember", back_populates="user", cascade="all, delete-orphan"
    )
    chats = relationship("Chat", back_populates="owner", cascade="all, delete-orphan")


class ServiceType(PyEnum):
    FRONTEND = "frontend"
    BACKEND = "backend"
    OTHER = "other"

class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    stack_id = Column(Integer, ForeignKey("stacks.id"), nullable=False)
    service_type = Column(Enum(ServiceType), nullable=False, default=ServiceType.OTHER)

    docker_container_id = Column(String, nullable=True)
    docker_port = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # relationships
    project = relationship("Project", back_populates="services")
    stack = relationship("Stack")

class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=True)
    custom_instructions = Column(Text, nullable=True)

    modal_sandbox_last_used_at = Column(DateTime(timezone=True), nullable=True)
    modal_sandbox_id = Column(String, nullable=True)
    modal_sandbox_expires_at = Column(DateTime(timezone=True), nullable=True)
    modal_volume_label = Column(String, nullable=True)
    # handy debugging flag to prevent cleanup
    modal_never_cleanup = Column(Boolean, nullable=True, default=False)

    team_id = Column(
        Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    stack_id = Column(Integer, ForeignKey("stacks.id"), nullable=False)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    owner = relationship("User", back_populates="projects")

    team = relationship("Team", back_populates="projects")
    stack = relationship("Stack", back_populates="projects")
    chats = relationship("Chat", back_populates="project", cascade="all, delete-orphan")
    services = relationship("Service", back_populates="project", cascade="all, delete-orphan")

class TeamPlanType(PyEnum):
    STANDARD = "standard"


class Team(TimestampMixin, Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    plan_type = Column(
        Enum(TeamPlanType), nullable=False, default=TeamPlanType.STANDARD
    )
    credits = Column(Integer, nullable=False, default=0)

    # Relationships
    members = relationship(
        "TeamMember", back_populates="team", cascade="all, delete-orphan"
    )
    projects = relationship(
        "Project", back_populates="team", cascade="all, delete-orphan"
    )
    invites = relationship(
        "TeamInvite", back_populates="team", cascade="all, delete-orphan"
    )
    credit_purchases = relationship(
        "TeamCreditPurchase", back_populates="team", cascade="all, delete-orphan"
    )


class TeamRole(PyEnum):
    ADMIN = "admin"
    MEMBER = "member"


class TeamMember(TimestampMixin, Base):
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(
        Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role = Column(Enum(TeamRole), nullable=False, default=TeamRole.MEMBER)

    # Relationships
    team = relationship("Team", back_populates="members")
    user = relationship("User", back_populates="team_memberships")


class StackType(PyEnum):
    FRONTEND = "frontend"
    BACKEND = "backend"
    OTHER = "other"
class Stack(TimestampMixin, Base):
    __tablename__ = "stacks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=False)
    prompt = Column(Text, nullable=False)
    from_registry = Column(String, nullable=False)
    sandbox_init_cmd = Column(Text, nullable=False)
    sandbox_start_cmd = Column(Text, nullable=False)
    pack_hash = Column(String, nullable=False)
    setup_time_seconds = Column(Integer, nullable=False)
    preview_url = Column(String, nullable=True)  
    stack_type = Column(Enum(StackType), nullable=False, default=StackType.OTHER)
    # Relationships
    projects = relationship("Project", back_populates="stack")
    prepared_sandboxes = relationship(
        "PreparedSandbox", back_populates="stack", cascade="all, delete-orphan"
    )
   


class Chat(TimestampMixin, Base):
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    project_id = Column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    is_public = Column(Boolean, nullable=False, default=False)
    public_share_id = Column(String, unique=True, nullable=True, index=True)

    # Relationships
    project = relationship("Project", back_populates="chats")
    owner = relationship("User", back_populates="chats")
    messages = relationship(
        "Message", back_populates="chat", cascade="all, delete-orphan"
    )


class Message(TimestampMixin, Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    images = Column(ARRAY(String), nullable=True)

    chat_id = Column(
        Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False
    )
    chat = relationship("Chat", back_populates="messages")


class PreparedSandbox(TimestampMixin, Base):
    __tablename__ = "prepared_sandboxes"

    id = Column(Integer, primary_key=True, index=True)
    modal_sandbox_id = Column(String, nullable=True)
    modal_volume_label = Column(String, nullable=True)
    pack_hash = Column(String, nullable=True)

    stack_id = Column(Integer, ForeignKey("stacks.id"), nullable=False)
    stack = relationship("Stack", back_populates="prepared_sandboxes")


class TeamInvite(TimestampMixin, Base):
    __tablename__ = "team_invites"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(
        Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    invite_code = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_by_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Relationships
    team = relationship("Team", back_populates="invites")
    created_by = relationship("User", backref="created_invites")


class TeamCreditPurchase(TimestampMixin, Base):
    __tablename__ = "team_credit_purchases"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(
        Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    amount = Column(Integer, nullable=False)  # Number of credits purchased
    price_cents = Column(Integer, nullable=False)  # Price paid in cents
    external_payment_id = Column(String, nullable=False)  # External payment reference

    # Relationship
    team = relationship("Team", back_populates="credit_purchases")


class CreditDailyPool(TimestampMixin, Base):
    __tablename__ = "credit_daily_pools"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime(timezone=True), nullable=False, unique=True, index=True)
    credits_remaining = Column(Integer, nullable=False, default=0)


