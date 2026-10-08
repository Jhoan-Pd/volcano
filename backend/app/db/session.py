"""Motor y sesión de SQLAlchemy."""
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def crear_engine(url: str):
    if url.startswith("sqlite"):
        eng = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(eng, "connect")
        def _fk_on(dbapi_conn, _):  # SQLite no valida llaves foráneas si no se activa
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        return eng
    # pool_pre_ping: Neon/Supabase cierran conexiones inactivas; así se detectan antes de usarlas.
    # prepare_threshold=None: desactiva sentencias preparadas de psycopg3, que fallan detrás de
    # poolers en modo transacción (PgBouncer de Neon, Supavisor de Supabase).
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5, pool_recycle=300,
                         connect_args={"prepare_threshold": None})


engine = crear_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
