import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy import text
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


def _sqlite_columns(connection, table_name: str) -> set[str]:
    rows = connection.execute(text(f"PRAGMA table_info({table_name})")).mappings().all()
    return {row["name"] for row in rows}


def _ensure_sqlite_schema_compatibility(bind) -> None:
    if bind.dialect.name != "sqlite":
        return

    column_patches = {
        "customers": {
            "dnd_until": "ALTER TABLE customers ADD COLUMN dnd_until DATETIME",
            "dnd_channels": "ALTER TABLE customers ADD COLUMN dnd_channels TEXT",
            "dnd_message_types": "ALTER TABLE customers ADD COLUMN dnd_message_types TEXT",
            "external_userid": "ALTER TABLE customers ADD COLUMN external_userid VARCHAR(120)",
            "push_consent_status": (
                "ALTER TABLE customers ADD COLUMN push_consent_status VARCHAR(40) DEFAULT 'unknown'"
            ),
        },
        "pets": {
            "vaccine_next_date": "ALTER TABLE pets ADD COLUMN vaccine_next_date DATE",
            "deworming_last_date": "ALTER TABLE pets ADD COLUMN deworming_last_date DATE",
        },
        "follow_tasks": {
            "decision_card": "ALTER TABLE follow_tasks ADD COLUMN decision_card TEXT",
            "send_mode": "ALTER TABLE follow_tasks ADD COLUMN send_mode VARCHAR(40) DEFAULT 'manual_confirm'",
        },
        "content_items": {
            "hashtags": "ALTER TABLE content_items ADD COLUMN hashtags TEXT",
            "image_prompt": "ALTER TABLE content_items ADD COLUMN image_prompt TEXT",
            "scheduled_date": "ALTER TABLE content_items ADD COLUMN scheduled_date DATE",
            "interaction_data": "ALTER TABLE content_items ADD COLUMN interaction_data TEXT",
        },
        "staff": {
            "wecom_userid": "ALTER TABLE staff ADD COLUMN wecom_userid VARCHAR(120)",
            "wecom_corp_id": "ALTER TABLE staff ADD COLUMN wecom_corp_id VARCHAR(120)",
            "wecom_name": "ALTER TABLE staff ADD COLUMN wecom_name VARCHAR(120)",
            "wecom_avatar": "ALTER TABLE staff ADD COLUMN wecom_avatar VARCHAR(255)",
            "wecom_bound_at": "ALTER TABLE staff ADD COLUMN wecom_bound_at DATETIME",
        },
    }
    with bind.begin() as connection:
        for table_name, patches in column_patches.items():
            columns = _sqlite_columns(connection, table_name)
            if not columns:
                continue
            for column_name, statement in patches.items():
                if column_name not in columns:
                    connection.execute(text(statement))


engine = _create_engine(_current_database_url())
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    global engine, SessionLocal
    database_url = _current_database_url()
    engine = _create_engine(database_url)
    SessionLocal.configure(bind=engine)
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_schema_compatibility(engine)
