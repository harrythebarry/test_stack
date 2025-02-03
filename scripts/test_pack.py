"""
python ../scripts/test_pack.py
"""

import sys

sys.path.append("../")
sys.path.append("../backend")

import asyncio
import modal
import uuid
from backend.sandbox.default_packs import (
    StackPack,
    _SETUP_COMMON_CMD,
    _START_ANGULAR_CMD,
)
from backend.sandbox.sandbox import app

# Define your test pack here
TEST_PACK = StackPack(
    title="Test",
    description="Test",
    from_registry="ghcr.io/sshh12/prompt-stack-pack-angular-vanilla@sha256:46a870b62a584712f90749a3adcc9c4496437d2d7130991cee1030eea42bd46c",
    sandbox_init_cmd=_SETUP_COMMON_CMD,
    sandbox_start_cmd=_START_ANGULAR_CMD,
    prompt="",
    setup_time_seconds=60,
)


async def main():
    vol_id = None
    sb = None
    try:
        print("Creating sandbox for test pack...")

        # Create volume
        vol_id = f"prompt-stack-vol-{str(uuid.uuid4())}"
        vol = modal.Volume.from_name(vol_id, create_if_missing=True)
        print(f"Created volume: {vol_id}")

        # Create init sandbox
        image = modal.Image.from_registry(TEST_PACK.from_registry, add_python=None)
        init_sb = await modal.Sandbox.create.aio(
            "sh",
            "-c",
            TEST_PACK.sandbox_init_cmd,
            app=app,
            volumes={"/app": vol},
            image=image,
            timeout=5 * 60,
            cpu=0.125,
            memory=256,
        )
        print(f"Running init sandbox (id={init_sb.object_id})")
        await init_sb.wait.aio()

        # Create start sandbox
        sb = await modal.Sandbox.create.aio(
            "sh",
            "-c",
            TEST_PACK.sandbox_start_cmd,
            app=app,
            volumes={"/app": vol},
            image=image,
            encrypted_ports=[3000],
            timeout=60 * 60,
            cpu=0.125,
            memory=1024 * 2,
        )
        print(f"Created start sandbox (id={sb.object_id})")

        print("Waiting for sandbox to be ready...")
        await asyncio.sleep(5)  # Give it a moment to start

        tunnels = await sb.tunnels.aio()
        tunnel_url = tunnels[3000].url
        print(f"\nSandbox is ready!")
        print(f"Tunnel URL: {tunnel_url}")

        print("\nPress Ctrl+C to terminate the sandbox")
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\nTerminating sandbox...")
    except Exception as e:
        print(f"\nError occurred: {e}")
    finally:
        if sb:
            await sb.terminate.aio()
        if vol_id:
            await modal.Volume.delete.aio(label=vol_id)
        print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
