from collections.abc import Generator

from app.database import SessionLocal, init_db


def get_db() -> Generator:
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
