from typing import Optional

from sqlalchemy.orm import joinedload
from sqlalchemy.orm import Session
from sqlalchemy import and_

from db.models import Chat, User, Project, Team, TeamMember


def get_chat_for_user(db: Session, chat_id: int, current_user: User) -> Optional[Chat]:
    chat = (
        db.query(Chat)
        .filter(Chat.id == chat_id, Chat.user_id == current_user.id)
        .options(joinedload(Chat.messages), joinedload(Chat.project))
        .first()
    )
    return chat


def get_project_for_user(
    db: Session, team_id: int, project_id: int, current_user: User
) -> Optional[Project]:
    project = (
        db.query(Project)
        .join(Team, Project.team_id == Team.id)
        .join(TeamMember, Team.id == TeamMember.team_id)
        .filter(
            and_(
                Team.id == team_id,
                Project.id == project_id,
                TeamMember.user_id == current_user.id,
                TeamMember.team_id == Project.team_id,
            ),
        )
        .first()
    )
    return project
