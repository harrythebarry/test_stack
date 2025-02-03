# backend/routers/projects.py

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from typing import List, Tuple
from sqlalchemy import and_
from sse_starlette.sse import EventSourceResponse
from fastapi.responses import StreamingResponse, JSONResponse
import requests
import json
import re
import asyncio

from sandbox.local_docker_sandbox import LocalDockerSandbox
from db.database import get_db
from db.models import User, Project, Team, TeamMember, Chat, Service, Stack
from db.queries import get_project_for_user
from schemas.models import (
    ProjectResponse,
    ProjectFileContentResponse,
    ProjectGitLogResponse,
    ProjectUpdate,
    ChatResponse,
)
from sandbox.sandbox_handler import get_sandbox_for_project
from routers.auth import get_current_user_from_token

router = APIRouter(prefix="/api/teams/{team_id}/projects", tags=["projects"])


@router.get("", response_model=List[ProjectResponse])
async def get_user_projects(
    team_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
):
    """
    List all projects in a team that the current user is a member of.
    """
    projects = (
        db.query(Project)
        .join(Team, Project.team_id == Team.id)
        .join(TeamMember, Team.id == TeamMember.team_id)
        .filter(
            and_(
                Team.id == team_id,
                TeamMember.user_id == current_user.id,
                TeamMember.team_id == Project.team_id,
            ),
        )
        .all()
    )
    return projects


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    team_id: int,
    project_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
):
    """
    Retrieve one project if the user is a member of the team.
    """
    project = get_project_for_user(db, team_id, project_id, current_user)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    team_id: int,
    project_id: int,
    project_data: ProjectUpdate,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
):
    """
    Update project name/description/custom_instructions
    """
    project = get_project_for_user(db, team_id, project_id, current_user)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if project_data.name is not None:
        project.name = project_data.name
    if project_data.description is not None:
        project.description = project_data.description
    if project_data.custom_instructions is not None:
        project.custom_instructions = project_data.custom_instructions

    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}/file/{path:path}", response_model=ProjectFileContentResponse)
async def get_project_file(
    team_id: int,
    project_id: int,
    path: str,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
):
    """
    Read file contents from a project's sandbox by path.
    """
    project_obj = get_project_for_user(db, team_id, project_id, current_user)
    if project_obj is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Retrieve all sandboxes for the project
    sandboxes = await get_sandbox_for_project(project_obj, create_if_missing=False)

    # Decide which sandbox to interact with based on your logic
    # For example, target the backend service's sandbox
    backend_sandbox = next(
        (sb for sb in sandboxes if isinstance(sb, LocalDockerSandbox) and sb.service.service_type == "BACKEND"),
        None
    )

    if not backend_sandbox:
        raise HTTPException(status_code=404, detail="Backend sandbox not found.")

    content = await backend_sandbox.run_command(f"cat /app/{path}")

    if not content:
        raise HTTPException(status_code=404, detail="File not found or empty.")

    return ProjectFileContentResponse(path=path, content=content)


@router.get("/{project_id}/git-log", response_model=ProjectGitLogResponse)
async def get_project_git_log(
    team_id: int,
    project_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
):
    """
    Return the project's git log as a structured list.
    """
    project_obj = get_project_for_user(db, team_id, project_id, current_user)
    if project_obj is None:
        raise HTTPException(status_code=404, detail="Project not found")

    sandboxes = await get_sandbox_for_project(project_obj, create_if_missing=False)

    # Target the backend sandbox for git operations
    backend_sandbox = next(
        (sb for sb in sandboxes if isinstance(sb, LocalDockerSandbox) and sb.service.service_type == "BACKEND"),
        None
    )

    if not backend_sandbox:
        raise HTTPException(status_code=404, detail="Backend sandbox not found.")

    content = await backend_sandbox.run_command("git log --oneline")

    if not content.strip():
        return ProjectGitLogResponse(lines=[])

    lines = content.strip().split("\n")
    return ProjectGitLogResponse(lines=lines)


@router.get("/{project_id}/chats", response_model=List[ChatResponse])
async def get_project_chats(
    team_id: int,
    project_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
):
    """
    List all chats for the project that belong to the current user.
    """
    project = get_project_for_user(db, team_id, project_id, current_user)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    chats = (
        db.query(Chat)
        .filter(
            and_(
                Chat.project_id == project_id,
                Chat.user_id == current_user.id,
            )
        )
        .order_by(Chat.created_at.desc())
        .all()
    )
    return chats


@router.post("/{project_id}/restart")
async def restart_project(
    team_id: int,
    project_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
):
    """
    Forcibly kill + remove the sandbox for a project, so a fresh sandbox can start next time.
    """
    project = get_project_for_user(db, team_id, project_id, current_user)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    sandboxes = await get_sandbox_for_project(project, create_if_missing=False)

    for sb in sandboxes:
        if isinstance(sb, LocalDockerSandbox):
            await sb.destroy_container()

    return {"message": f"Project {project_id} sandbox(s) restarted."}


@router.delete("/{project_id}")
async def delete_project(
    team_id: int,
    project_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
):
    """
    Permanently delete a project, all its chats, and destroy its sandbox resources.
    """
    project = get_project_for_user(db, team_id, project_id, current_user)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Remove from DB
    db.delete(project)

    # Also remove any associated chats
    chats = db.query(Chat).filter(Chat.project_id == project_id).all()
    for c in chats:
        db.delete(c)
    db.commit()

    # Remove sandbox resources
    sandboxes = await get_sandbox_for_project(project, create_if_missing=False)
    for sb in sandboxes:
        if isinstance(sb, LocalDockerSandbox):
            await sb.destroy_container()

    return {"message": f"Project {project_id} deleted successfully"}


@router.post("/{project_id}/zip")
async def generate_project_zip(
    team_id: int,
    project_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
):
    """
    Example of zipping up the code in /app, ignoring certain paths.
    For Docker or Modal, we get the sandbox if it's running, run zip commands, return a URL to download.
    """
    project_obj = get_project_for_user(db, team_id, project_id, current_user)
    if project_obj is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Retrieve all sandboxes for the project
    sandboxes = await get_sandbox_for_project(project_obj, create_if_missing=False)

    # Target the backend sandbox for zipping
    backend_sandbox = next(
        (sb for sb in sandboxes if isinstance(sb, LocalDockerSandbox) and sb.service.service_type == "BACKEND"),
        None
    )

    if not backend_sandbox:
        raise HTTPException(status_code=404, detail="Backend sandbox not found.")

    git_sha = await backend_sandbox.run_command("git rev-parse HEAD")
    git_sha = git_sha.strip()[:10] if git_sha.strip() else "init"

    zip_name = f"app-{project_obj.id}-{git_sha}.zip".replace(" ", "-")

    exclude_content = """
**/node_modules/**
**/.next/**
**/build/**
git.log
**/git.log
tmp
tmp/
**/tmp
**/tmp/
.git
.git/
**/.git
**/.git/
.env
""".strip()

    await backend_sandbox.run_command(f"echo '{exclude_content}' > /tmp/zip-exclude.txt")
    await backend_sandbox.run_command("mkdir -p /app/tmp")
    await backend_sandbox.run_command("find /app -type d -name 'tmp' -exec rm -rf {} +")
    await backend_sandbox.run_command(
        f"cd /app && zip -r /app/tmp/{zip_name} . -x@/tmp/zip-exclude.txt"
    )

    return JSONResponse({"url": f"/api/teams/{team_id}/projects/{project_id}/download-zip?path={zip_name}"})


@router.get("/{project_id}/download-zip")
async def get_project_download_zip(
    team_id: int,
    project_id: int,
    path: str = Query(..., description="Path to the zip file"),
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
):
    """
    Stream the generated zip file from /app/tmp/<filename>.
    """
    project_obj = db.query(Project).filter(Project.id == project_id).first()
    if project_obj is None:
        raise HTTPException(status_code=404, detail="Project not found")

    expected_prefix = f"app-{project_id}-"
    if not (
        path.startswith(expected_prefix)
        and path.endswith(".zip")
        and "/" not in path
        and "\\" not in path
        and ".." not in path
        and re.match(r"^app-\d+-[a-f0-9]{1,10}\.zip$", path)
    ):
        raise HTTPException(status_code=400, detail="Invalid zip file path")

    # Retrieve all sandboxes for the project
    sandboxes = await get_sandbox_for_project(project_obj, create_if_missing=False)

    # Target the backend sandbox for downloading
    backend_sandbox = next(
        (sb for sb in sandboxes if isinstance(sb, LocalDockerSandbox) and sb.service.service_type == "BACKEND"),
        None
    )

    if not backend_sandbox:
        raise HTTPException(status_code=404, detail="Backend sandbox not found.")

    try:
        file_size_str = await backend_sandbox.run_command(f"stat -c%s /app/tmp/{path}")
        file_size = int(file_size_str.strip())

        async def _stream_zip():
            try:
                async for chunk in backend_sandbox.stream_file_contents(
                    f"/app/tmp/{path}",
                    binary_mode=True
                ):
                    yield chunk
            finally:
                # Optionally remove the zip file after streaming
                await backend_sandbox.run_command(f"rm -f /app/tmp/{path}")

        return StreamingResponse(
            _stream_zip(),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{path}"',
                "Content-Length": str(file_size),
            },
        )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error accessing zip file: {str(e)}"
        )


@router.get("/{project_id}/deploy-status/github")
async def deploy_status_github(
    team_id: int,
    project_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
):
    """
    Example of checking if the project has a remote origin set
    and if .env has GITHUB_TOKEN, etc.
    """
    project_obj = get_project_for_user(db, team_id, project_id, current_user)
    if project_obj is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Retrieve all sandboxes for the project
    sandboxes = await get_sandbox_for_project(project_obj, create_if_missing=False)

    # Target the backend sandbox for deployment status
    backend_sandbox = next(
        (sb for sb in sandboxes if isinstance(sb, LocalDockerSandbox) and sb.service.service_type == "BACKEND"),
        None
    )

    if not backend_sandbox:
        raise HTTPException(status_code=404, detail="Backend sandbox not found.")

    remotes = await backend_sandbox.run_command("git remote -v")
    has_origin = "origin" in remotes
    env_text = await backend_sandbox.run_command("cat /app/.env")
    has_token = "GITHUB_TOKEN" in env_text

    # Parse the .env for GITHUB_REPO
    try:
        repo_name = re.search(r"GITHUB_REPO=(.*)", env_text).group(1)
    except Exception:
        repo_name = None

    return JSONResponse({"created": has_token and has_origin, "repo_name": repo_name})


@router.post("/{project_id}/deploy-push/github")
async def deploy_push_github(
    team_id: int,
    project_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
):
    """
    Push the code to GitHub remote origin main.
    """
    project_obj = get_project_for_user(db, team_id, project_id, current_user)
    if project_obj is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Retrieve all sandboxes for the project
    sandboxes = await get_sandbox_for_project(project_obj, create_if_missing=False)

    # Target the backend sandbox for git push
    backend_sandbox = next(
        (sb for sb in sandboxes if isinstance(sb, LocalDockerSandbox) and sb.service.service_type == "BACKEND"),
        None
    )

    if not backend_sandbox:
        raise HTTPException(status_code=404, detail="Backend sandbox not found.")

    out = await backend_sandbox.run_command("git push -u origin main --force")
    print(out)
    return JSONResponse({"done": True})


@router.get("/{project_id}/deploy-create/github")
async def deploy_create_github(
    team_id: int,
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    SSE endpoint that:
      1) calls GitHub API to create a repo
      2) sets up local git remote
      3) pushes the code
      4) updates /app/.env with GITHUB_TOKEN, etc.
    """
    token = request.query_params.get("token")
    if not token:
        raise HTTPException(status_code=400, detail="Missing token parameter")

    current_user = await get_current_user_from_token(token, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Invalid token")

    project_obj = get_project_for_user(db, team_id, project_id, current_user)
    if project_obj is None:
        raise HTTPException(status_code=404, detail="Project not found")

    github_token = request.query_params.get("githubToken")
    if not github_token:
        raise HTTPException(status_code=400, detail="Missing githubToken")

    repo_name = project_obj.name.replace(" ", "-").lower()

    async def event_generator():
        sandboxes = await get_sandbox_for_project(project_obj, create_if_missing=False)

        # Target the backend sandbox for deployment
        backend_sandbox = next(
            (sb for sb in sandboxes if isinstance(sb, LocalDockerSandbox) and sb.service.service_type == "BACKEND"),
            None
        )

        if not backend_sandbox:
            yield {"event": "message", "data": json.dumps({"message": "Backend sandbox not found."})}
            return

        yield {"event": "message", "data": json.dumps({"message": "Creating repository..."})}

        remotes = await backend_sandbox.run_command("git remote -v")
        if "origin" not in remotes:
            create_repo_response = requests.post(
                "https://api.github.com/user/repos",
                headers={
                    "Authorization": f"Bearer {github_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                json={"name": repo_name},
            ).json()

            if "message" in create_repo_response and "already exists" in create_repo_response["message"].lower():
                # Repository already exists, retrieve owner info
                owner_info = requests.get(
                    "https://api.github.com/user",
                    headers={
                        "Authorization": f"Bearer {github_token}",
                        "Accept": "application/vnd.github.v3+json",
                    },
                ).json()
                owner_name = owner_info.get("login")
                full_name = f"{owner_name}/{repo_name}" if owner_name else repo_name
            else:
                full_name = create_repo_response.get("full_name", repo_name)

            yield {"event": "message", "data": json.dumps({"message": "Connecting to repository..."})}

            # Add remote origin with authentication
            await backend_sandbox.run_command(
                f"git remote add origin https://{owner_name}:{github_token}@github.com/{full_name}.git"
            )
            yield {"event": "message", "data": json.dumps({"message": "Pushing to repository..."})}

            # Push to GitHub
            await backend_sandbox.run_command("git branch -M main")
            await backend_sandbox.run_command("git push -u origin main")

            # Update .env with GitHub details
            await backend_sandbox.run_command(
                f"echo -n 'GITHUB_TOKEN={github_token}\\nGITHUB_REPO={full_name}\\nGITHUB_OWNER={owner_name}\\n' >> /app/.env"
            )

        yield {"event": "message", "data": json.dumps({"done": True})}

    return EventSourceResponse(event_generator())


@router.get("/{project_id}/env-vars")
async def get_project_env_vars(
    team_id: int,
    project_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
):
    """
    Return environment variables from /app/.env as key->value map.
    """
    project_obj = get_project_for_user(db, team_id, project_id, current_user)
    if not project_obj:
        raise HTTPException(status_code=404, detail="Project not found")

    # Retrieve all sandboxes for the project
    sandboxes = await get_sandbox_for_project(project_obj, create_if_missing=False)

    # Target the backend sandbox for environment variables
    backend_sandbox = next(
        (sb for sb in sandboxes if isinstance(sb, LocalDockerSandbox) and sb.service.service_type == "BACKEND"),
        None
    )

    if not backend_sandbox:
        raise HTTPException(status_code=404, detail="Backend sandbox not found.")

    content = await backend_sandbox.run_command("cat /app/.env")
    if not content:
        return JSONResponse({"env_vars": {}})

    env_vars = {}
    for line in content.decode("utf-8").splitlines():
        if "=" in line:
            key, val = line.split("=", 1)
            env_vars[key.strip()] = val.strip()

    return JSONResponse({"env_vars": env_vars})


@router.post("/{project_id}/env-vars")
async def update_project_env_vars(
    team_id: int,
    project_id: int,
    request: Request,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
):
    """
    Write environment variables to /app/.env
    """
    project_obj = get_project_for_user(db, team_id, project_id, current_user)
    if not project_obj:
        raise HTTPException(status_code=404, detail="Project not found")

    body = await request.json()
    env_data = body.get("env_vars", {})
    # Join them
    env_text = "\n".join(f"{k}={v}" for k, v in env_data.items())

    # Retrieve all sandboxes for the project
    sandboxes = await get_sandbox_for_project(project_obj, create_if_missing=False)

    # Target the backend sandbox for environment variables
    backend_sandbox = next(
        (sb for sb in sandboxes if isinstance(sb, LocalDockerSandbox) and sb.service.service_type == "BACKEND"),
        None
    )

    if not backend_sandbox:
        raise HTTPException(status_code=404, detail="Backend sandbox not found.")

    await backend_sandbox.run_command(f"echo -e '{env_text}' > /app/.env")

    return JSONResponse({"message": "Environment variables updated successfully"})


@router.get("/{project_id}/preview-url")
def get_preview_url(
    team_id: int,
    project_id: int,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db),
):
    """
    If your code has multiple services (one labeled FRONTEND),
    return the preview_url from that service.
    """
    project_obj = get_project_for_user(db, team_id, project_id, current_user)
    if not project_obj:
        raise HTTPException(status_code=404, detail="Not found")

    frontend_service = next(
        (svc for svc in project_obj.services if svc.service_type == "FRONTEND"),
        None
    )

    if not frontend_service:
        raise HTTPException(status_code=404, detail="No frontend service found.")

    return {"preview_url": frontend_service.preview_url or ""}
