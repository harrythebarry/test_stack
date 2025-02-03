from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import aioboto3

from config import (
    DATABASE_URL,
    DB_POOL_SIZE,
    DB_MAX_OVERFLOW,
    DB_POOL_RECYCLE,
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_REGION,
    RUN_STACK_SYNC_ON_START,
)

engine = create_engine(
    DATABASE_URL,
    pool_size=DB_POOL_SIZE,  # Configurable pool size
    max_overflow=DB_MAX_OVERFLOW,  # Configurable overflow
    pool_recycle=DB_POOL_RECYCLE,  # Configurable connection recycling
)

SessionLocalAutoCommit = sessionmaker(autocommit=True, autoflush=True, bind=engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def _try_init_stacks():
    # Initialize database session
    db = SessionLocal()
    try:
        from sandbox.default_packs import PACKS
        from db.models import Stack

        for pack in PACKS:
            stack = db.query(Stack).filter(Stack.title == pack.title).first()
            if stack:
                # Update existing stack
                stack.description = pack.description
                stack.from_registry = pack.from_registry
                stack.sandbox_init_cmd = pack.sandbox_init_cmd
                stack.sandbox_start_cmd = pack.sandbox_start_cmd
                stack.prompt = pack.prompt
                stack.pack_hash = pack.pack_hash
                stack.setup_time_seconds = pack.setup_time_seconds
            else:
                # Insert new stack
                stack = Stack(
                    title=pack.title,
                    description=pack.description,
                    from_registry=pack.from_registry,
                    sandbox_init_cmd=pack.sandbox_init_cmd,
                    sandbox_start_cmd=pack.sandbox_start_cmd,
                    prompt=pack.prompt,
                    pack_hash=pack.pack_hash,
                    setup_time_seconds=pack.setup_time_seconds,
                )
                db.add(stack)
        db.commit()
    finally:
        db.close()


def init_db():
    # Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    if RUN_STACK_SYNC_ON_START:
        _try_init_stacks()


def get_db(auto_commit=False):
    if auto_commit:
        db = SessionLocalAutoCommit()
    else:
        db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_aws_client():
    client = aioboto3.Session(
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
    )
    yield client
