"""
This file sets up the connection to Postgres using SQLAlchemy,
with an automatic SQLite fallback if local Postgres is not running.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import logging

from app.config import settings, BASE_DIR

logger = logging.getLogger(__name__)

# Try connecting to Postgres; if unavailable/auth fails, fall back to SQLite
try:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    with engine.connect() as conn:
        pass
    logger.info("Successfully connected to Postgres database.")
except Exception as exc:
    logger.warning(f"Postgres connection failed ({exc}). Falling back to local SQLite database.")
    sqlite_url = "sqlite:///" + str(BASE_DIR / "vendor_intelligence.db")
    engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """
    FastAPI dependency: gives each request a fresh DB session
    and always closes it afterwards, even if an error happens.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
