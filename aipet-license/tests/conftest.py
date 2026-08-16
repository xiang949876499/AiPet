import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture()
def license_db(tmp_path, monkeypatch):
    import admin.routes as admin_routes
    import database
    import server
    from models import Base

    engine = create_engine(
        f"sqlite:///{tmp_path / 'license-test.db'}",
        connect_args={"check_same_thread": False},
    )
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", testing_session)
    monkeypatch.setattr(server, "SessionLocal", testing_session)
    monkeypatch.setattr(admin_routes, "SessionLocal", testing_session)
    server.app.dependency_overrides.clear()
    yield testing_session
    server.app.dependency_overrides.clear()


@pytest.fixture()
def client(license_db):
    import server
    from fastapi.testclient import TestClient

    return TestClient(server.app)
