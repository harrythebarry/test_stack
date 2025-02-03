"""
python ../scripts/add_team_admin.py (--project-name <project_name> | --chat-id <chat_id>) <username>
"""

import sys

sys.path.append("../")
sys.path.append("../backend")

import sys
import argparse
from sqlalchemy import select
from backend.db.database import SessionLocal
from backend.db.models import Project, User, TeamMember, TeamRole, Chat


def confirm_action(message: str) -> bool:
    """Ask for user confirmation."""
    while True:
        response = input(f"{message} [y/N]: ").lower().strip()
        if response in ["y", "yes"]:
            return True
        if response in ["", "n", "no"]:
            return False


def select_project(projects):
    """Let user select from multiple matching projects."""
    print("\nMultiple matching projects found:")
    for idx, project in enumerate(projects, 1):
        print(f"{idx}. {project.name} (id: {project.id})")

    while True:
        try:
            choice = input("\nSelect project number (or 'q' to quit): ")
            if choice.lower() == "q":
                sys.exit(0)

            idx = int(choice)
            if 1 <= idx <= len(projects):
                return projects[idx - 1]
            print("Invalid selection. Please try again.")
        except ValueError:
            print("Please enter a valid number.")


def get_project_by_name(db, project_name: str) -> Project:
    """Get project by name, handling multiple matches."""
    projects = (
        db.execute(select(Project).where(Project.name.ilike(project_name)))
        .scalars()
        .all()
    )

    if not projects:
        print(f"Error: Project '{project_name}' not found", file=sys.stderr)
        sys.exit(1)

    return projects[0] if len(projects) == 1 else select_project(projects)


def get_project_by_chat_id(db, chat_id: int) -> Project:
    """Get project associated with a chat ID."""
    chat = db.execute(select(Chat).where(Chat.id == chat_id)).scalar_one_or_none()

    if not chat:
        print(f"Error: Chat with ID '{chat_id}' not found", file=sys.stderr)
        sys.exit(1)

    return chat.project


def add_team_admin(project_identifier: dict, username: str):
    """Add a user as an admin to the team associated with a project.

    Args:
        project_identifier: Dict with either 'project_name' or 'chat_id'
        username: Username of the user to add as admin
    """
    db = SessionLocal()

    try:
        # Get project based on provided identifier
        if "project_name" in project_identifier:
            project = get_project_by_name(db, project_identifier["project_name"])
        else:
            project = get_project_by_chat_id(db, project_identifier["chat_id"])

        # Find user
        user = db.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()

        if not user:
            print(f"Error: User '{username}' not found", file=sys.stderr)
            sys.exit(1)

        # Check if user is already a member
        existing_member = db.execute(
            select(TeamMember).where(
                TeamMember.team_id == project.team_id, TeamMember.user_id == user.id
            )
        ).scalar_one_or_none()

        if existing_member:
            print(
                f"Error: User '{username}' is already a member of this team",
                file=sys.stderr,
            )
            sys.exit(1)

        # Confirm action
        if not confirm_action(
            f"Add user '{username}' as admin to team for project '{project.name}'?"
        ):
            print("Operation cancelled")
            sys.exit(0)

        # Add user as admin
        team_member = TeamMember(
            team_id=project.team_id, user_id=user.id, role=TeamRole.ADMIN
        )
        db.add(team_member)
        db.commit()

        print(
            f"Successfully added '{username}' as admin to team for project '{project.name}'"
        )

    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Add a user as an admin to the team associated with a project"
    )

    # Create mutually exclusive group for project identification
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--project-name", help="Name of the project (case insensitive)")
    group.add_argument("--chat-id", type=int, help="ID of the chat")

    parser.add_argument("username", help="Username of the user to add as admin")

    args = parser.parse_args()

    # Create project identifier dict based on provided args
    project_identifier = {}
    if args.project_name:
        project_identifier["project_name"] = args.project_name
    else:
        project_identifier["chat_id"] = args.chat_id

    add_team_admin(project_identifier, args.username)


if __name__ == "__main__":
    main()
