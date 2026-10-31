from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.config import settings, effective_database_url

DB_URL = effective_database_url(settings)
_is_sqlite = DB_URL.startswith("sqlite")
engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    # Supabase sits behind a pooler that drops idle connections; without
    # pre-ping the first request after a quiet spell fails with a stale socket.
    **({} if _is_sqlite else {"pool_pre_ping": True, "pool_recycle": 300}),
)

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, _):
    # PRAGMA is SQLite-only syntax. This listener fires for every engine, so on
    # Postgres it would raise on the first connection the app ever opens.
    if not _is_sqlite:
        return
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA journal_mode=WAL")
    cur.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
