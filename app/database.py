import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models import Base


def _ensure_sqlite_parent(database_url: str) -> None:
    if database_url.startswith("sqlite:///"):
        db_path = Path(database_url.removeprefix("sqlite:///"))
        if db_path.parent != Path("."):
            db_path.parent.mkdir(parents=True, exist_ok=True)


def _current_database_url() -> str:
    return os.getenv("DATABASE_URL", settings.database_url)


def _create_engine(database_url: str):
    _ensure_sqlite_parent(database_url)
    return create_engine(database_url, connect_args={"check_same_thread": False})


engine = _create_engine(_current_database_url())
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    global engine, SessionLocal
    database_url = _current_database_url()
    engine = _create_engine(database_url)
    SessionLocal.configure(bind=engine)
    Base.metadata.create_all(bind=engine)
