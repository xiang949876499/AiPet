from sqlalchemy import create_engine, text


def test_init_db_adds_missing_wecom_columns_to_existing_sqlite(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    legacy_engine = create_engine(f"sqlite:///{db_path}")
    with legacy_engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE stores (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR(120) NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE customers (
                    id INTEGER PRIMARY KEY,
                    store_id INTEGER NOT NULL,
                    name VARCHAR(80) NOT NULL,
                    phone VARCHAR(40),
                    wechat_name VARCHAR(80),
                    source VARCHAR(80),
                    tags TEXT,
                    last_visit_time DATETIME,
                    total_amount NUMERIC(10, 2),
                    visit_count INTEGER,
                    do_not_disturb BOOLEAN,
                    note TEXT
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE staff (
                    id INTEGER PRIMARY KEY,
                    store_id INTEGER NOT NULL,
                    name VARCHAR(80) NOT NULL,
                    role VARCHAR(40),
                    phone VARCHAR(40),
                    status VARCHAR(20)
                )
                """
            )
        )

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    from app.database import SessionLocal, init_db
    from app.models import Customer, PushTask, Staff

    init_db()
    session = SessionLocal()
    try:
        assert session.query(Customer).count() == 0
        assert session.query(Staff).count() == 0
        assert session.query(PushTask).count() == 0
    finally:
        session.close()
