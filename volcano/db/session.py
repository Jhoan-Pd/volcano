"""SQLAlchemy engine and session factory."""
from collections.abc import Generator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from volcano.shared.config import settings


def build_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        eng = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(eng, "connect")
        def _enable_foreign_keys(dbapi_conn, _):  # SQLite ignores foreign keys unless asked
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        return eng
    # pool_pre_ping: Neon closes idle connections; this detects them before they are used.
    # prepare_threshold=None: disables psycopg3 prepared statements, which break behind
    # transaction-mode poolers (Neon's PgBouncer).
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5, pool_recycle=300,
                         connect_args={"prepare_threshold": None})


engine = build_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
