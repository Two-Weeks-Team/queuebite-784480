import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from routes import router as api_router
from models import Base, get_async_engine

load_dotenv()

app = FastAPI(title="QueueBite API", version="0.1.0")

# In a real deployment you would restrict origins. For simplicity we allow all.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

@app.on_event("startup")
async def on_startup() -> None:
    """Create database tables on startup if they do not exist."""
    engine = get_async_engine()
    async with engine.begin() as conn:  # type: ignore[arg-type]
        await conn.run_sync(Base.metadata.create_all)

# The entry‑point used by Docker / DO App Platform
# uvicorn main:app --host 0.0.0.0 --port 8080
