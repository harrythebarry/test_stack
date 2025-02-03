from fastapi import APIRouter, Depends
from typing import List
from sqlalchemy.orm import Session

from db.database import get_db
from schemas.models import StackResponse
from db.models import Stack

router = APIRouter(prefix="/api/stacks", tags=["stacks"])


@router.get("", response_model=List[StackResponse])
async def get_stacks(db: Session = Depends(get_db)):
    """
    Get all available stacks that can be used as templates for new projects.
    """
    return db.query(Stack).all()
