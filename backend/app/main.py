"""
Entry point of the backend.
Run it with:  uvicorn app.main:app --reload   (from inside the backend/ folder)
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.database import engine, Base, SessionLocal
from app.config import settings
from app.routers import invoice, freight, rag, batches
from app import batch_processor

# Creates the Postgres/SQLite tables the first time the app starts
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Vendor Intelligence API",
    description="Predicts invoice risk and estimates freight cost with batch upload support.",
    version="1.1.0",
)


@app.on_event("startup")
def startup_event():
    """Run startup checks, including cleaning up stuck batch jobs >30 minutes old."""
    db = SessionLocal()
    try:
        batch_processor.cleanup_stuck_batches(db, max_minutes=30)
    finally:
        db.close()


# Lets the frontend call this API from the browser
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
app.include_router(batches.router)


@app.get("/api/health", tags=["Health"])
def health_check():
    """Simple endpoint to confirm the API and its dependencies are up."""
    return {"status": "ok"}


# --- Serve the frontend (optional convenience) ---
frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

