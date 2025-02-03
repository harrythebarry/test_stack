
from typing import List, Optional
from db.database import get_db
from sandbox.sandbox import BaseSandbox
from db.models import Project
from config import SANDBOX_PROVIDER
from sandbox.modal_sandbox import ModalSandbox
from sandbox.local_docker_sandbox import LocalDockerSandbox


async def get_sandbox_for_project(
    project: Project, create_if_missing: bool = True, service_id: Optional[int] = None
) -> List[BaseSandbox]:
    """
    A unified helper that returns either a ModalSandbox or LocalDockerSandbox
    for the given project and service, depending on config or DB state.

    Args:
        project (Project): The project instance.
        create_if_missing (bool): Whether to create the sandbox if it doesn't exist.
        service_id (Optional[int]): The specific service ID to get the sandbox for.

    Returns:
        BaseSandbox: The sandbox instance.
    """
    print("get_sandbox_for_project")

    if SANDBOX_PROVIDER == "docker":
        # Local Docker
        if service_id is None:
            # create all services
            sandboxes = []
            for service in project.services: 
                sb = LocalDockerSandbox(service)
                print("Sandbox creation started: ", sb)
                await sb.create_or_get_container(
                    image=service.stack.from_registry,
                    start_command=service.stack.sandbox_start_cmd
                )
                print("Sandbox creation completed : ", sb)
                if create_if_missing:
                    await sb.wait_for_up()
                sandboxes.append(sb)
            return sandboxes
        else:
            print("creating sandbox for service : ", service_id)
            service = next(
                (svc for svc in project.services if svc.id == service_id), None
            )
            if not service:
                raise ValueError(f"Service ID {service_id} not found in project {project.id}.")

            sb = LocalDockerSandbox(service)
            await sb.create_or_get_container(
                image=service.stack.from_registry,
                start_command=service.stack.sandbox_start_cmd
            )
            print("created sandbox for service : ", service_id)
            if create_if_missing:
                await sb.wait_for_up()
            print("waited for sandbox for service : ", service_id)
            return [sb]
    else:
        # Default: ModalSandbox (assuming single sandbox per project)
        sb = await ModalSandbox.get_or_create(project.id, create_if_missing=create_if_missing)
        await sb.wait_for_up()
        return [sb]