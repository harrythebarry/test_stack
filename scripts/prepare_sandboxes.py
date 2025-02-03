"""
Script to manually run the maintain_prepared_sandboxes task to prepare sandbox environments.
"""

import sys
import asyncio
import argparse

sys.path.append("../")
sys.path.append("../backend")

from backend.db.database import SessionLocal
from backend.tasks.tasks import maintain_prepared_sandboxes


async def prepare_sandboxes(dry_run: bool = False):
    """Run the maintain_prepared_sandboxes task."""
    db = SessionLocal()
    try:
        print("Starting sandbox preparation...")
        await maintain_prepared_sandboxes(db)
        print("Sandbox preparation completed successfully")
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Prepare sandbox environments for stacks"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making any changes",
    )
    args = parser.parse_args()

    asyncio.run(prepare_sandboxes(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
