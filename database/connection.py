import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, scoped_session

from config import DATABASE_URL

db_dir = os.path.dirname(DATABASE_URL.replace("sqlite:///", ""))
if db_dir:
    os.makedirs(db_dir, exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False,
)

SessionLocal = scoped_session(sessionmaker(bind=engine))


def get_session():
    session = SessionLocal()
    try:
        return session
    except Exception:
        session.close()
        raise


def init_db():
    from database.models import Base
    Base.metadata.create_all(bind=engine)

    _run_migrations()


def _run_migrations():
    columns = {c["name"] for c in inspect(engine).get_columns("sales")}
    if "anulada" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE sales ADD COLUMN anulada BOOLEAN DEFAULT 0"))
