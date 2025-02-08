from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.database import init_db, get_db
from contextlib import asynccontextmanager
import asyncio

from routers import (
    project_socket,
    auth,
    projects,
    stacks,
    teams,
    chats,
    uploads,
    mocks,
    stripe,
)




app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8000",
        "https://*.up.railway.app",
        "https://sparkstack.app",
        "https://*.sparkstack.app",
        "https://prompt-stack.sshh.io",
        "https://*.sshh.io",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(project_socket.router)
app.include_router(stacks.router)
app.include_router(teams.router)
app.include_router(chats.router)
app.include_router(uploads.router)
app.include_router(mocks.router)
app.include_router(stripe.router)

if __name__ == "__main__":
    init_db()
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
