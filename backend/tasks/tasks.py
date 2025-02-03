# tasks.py

import traceback
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import functools
import modal

from routers.project_socket import project_managers
from db.models import Project, PreparedSandbox, Stack
from config import TARGET_PREPARED_SANDBOXES_PER_STACK, SANDBOX_PROVIDER

# For pre-warmed Modal volumes:
from sandbox.modal_sandbox import ModalSandbox
# We'll also assume you have a local docker sandbox:
from sandbox.local_docker_sandbox import LocalDockerSandbox


def task_handler():
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                print(f"Error in {func.__name__}: {e}\n{traceback.format_exc()}")
                return None
        return wrapper
    return decorator


@task_handler()
async def cleanup_inactive_project_managers():
    """
    Closes inactive WebSocket ProjectManagers after X minutes.
    Unrelated to Docker or Modal specifically, so it stays as is.
    """
    to_remove = []
    for project_id, manager in project_managers.items():
        if manager.is_inactive():
            to_remove.append(project_id)

    for project_id in to_remove:
        await project_managers[project_id].kill()
        del project_managers[project_id]
        print(f"Cleaned up inactive project manager for project {project_id}")


@task_handler()
async def maintain_prepared_sandboxes(db: Session):
    """
    Only relevant for Modal usage, to keep a buffer of prepared sandboxes.
    If SANDBOX_PROVIDER == 'docker', we skip everything.
    """
    if SANDBOX_PROVIDER.lower() != "modal":
        # Skip if not modal
        return

    # Using Modal:
    stacks = db.query(Stack).all()
    for stack in stacks:
        psboxes = (
            db.query(PreparedSandbox)
            .filter(PreparedSandbox.stack_id == stack.id)
            .all()
        )
        psboxes_to_add = max(
            0, TARGET_PREPARED_SANDBOXES_PER_STACK - len(psboxes)
        )

        if psboxes_to_add > 0:
            print(
                f"Creating {psboxes_to_add} prepared sandboxes for stack "
                f"{stack.title} (id={stack.id})"
            )
            for _ in range(psboxes_to_add):
                sb, vol_id = await ModalSandbox.prepare_sandbox(stack)
                psbox = PreparedSandbox(
                    stack_id=stack.id,
                    modal_sandbox_id=sb.object_id,
                    modal_volume_label=vol_id,
                    pack_hash=stack.pack_hash,
                )
                db.add(psbox)
                db.commit()

    # Remove stale prepared sandboxes with mismatched pack_hash
    latest_stack_hashes = set(s.pack_hash for s in stacks)
    stale_psboxes = db.query(PreparedSandbox).filter(
        (PreparedSandbox.pack_hash.notin_(latest_stack_hashes))
        | (PreparedSandbox.pack_hash.is_(None))
    ).all()

    if stale_psboxes:
        print(
            f"Deleting {len(stale_psboxes)} prepared sandboxes with stale hashes"
        )
        for psb in stale_psboxes:
            db.delete(psb)
            db.commit()
            # remove the volume from Modal
            await modal.Volume.delete.aio(label=psb.modal_volume_label)


@task_handler()
async def clean_up_project_resources(db: Session):
    """
    For Modal: kills old sandboxes not used in 15+ min.
    For Docker: also kills containers for old projects.
    Checks Project.modal_sandbox_last_used_at as the "last used" time.
    """
    cutoff = datetime.now() - timedelta(minutes=15)

    # 1) For Modal
    if SANDBOX_PROVIDER.lower() == "modal":
        projects = (
            db.query(Project)
            .filter(
                Project.modal_sandbox_id.isnot(None),
                Project.modal_sandbox_last_used_at.isnot(None),
                Project.modal_sandbox_last_used_at < cutoff,
                (Project.modal_never_cleanup.is_(None) | ~Project.modal_never_cleanup),
            )
            .all()
        )
        if projects:
            print(f"Cleaning up old modal sandboxes for projects {[p.id for p in projects]}")
            for project in projects:
                # terminate
                await ModalSandbox.terminate_project_resources(project)
                project.modal_sandbox_id = None
                project.modal_sandbox_expires_at = None
                db.commit()

    # 2) For Docker
    else:
        # Example approach: find all projects where last_used < 15 min
        # and do a Docker-based cleanup
        projects = (
            db.query(Project)
            .filter(
                Project.modal_sandbox_last_used_at.isnot(None),
                Project.modal_sandbox_last_used_at < cutoff,
                (Project.modal_never_cleanup.is_(None) | ~Project.modal_never_cleanup),
            )
            .all()
        )
        if projects:
            print(f"Cleaning up old docker containers for projects {[p.id for p in projects]}")
            for project in projects:
                # kill Docker containers
                await LocalDockerSandbox.terminate_project_containers(project)
                # reset last used time or other fields
                project.modal_sandbox_last_used_at = None
                db.commit()
