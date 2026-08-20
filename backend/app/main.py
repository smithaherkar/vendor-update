"""
Entry point of the backend.
Run it with:  uvicorn app.main:app --reload   (from inside the backend/ folder)
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.database import engine, Base
from app.config import settings
from app.routers import invoice, freight, rag

# Creates the Postgres tables the first time the app starts, if they
# don't already exist. (For real production changes later, use Alembic.)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Vendor Intelligence API",
    description="Predicts invoice risk and estimates freight cost.",
    version="1.0.0",
)

# Lets the frontend (running on a different port) call this API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(invoice.router)
app.include_router(freight.router)
app.include_router(rag.router)


@app.get("/api/health", tags=["Health"])
def health_check():
    """Simple endpoint to confirm the API and its dependencies are up."""
    return {"status": "ok"}


# --- Serve the frontend (optional convenience) ---
# This lets you open http://localhost:8000/ and get the dashboard directly,
# with no separate frontend server needed.
frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
