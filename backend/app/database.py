import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATABASE_PATH = Path(os.environ.get("KALIBRO_DB", PROJECT_ROOT / "database" / "kalibro.db"))
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# Uploaded course material lives here, never in the repo.
UPLOAD_DIR = Path(os.environ.get("KALIBRO_UPLOADS", PROJECT_ROOT / "data" / "uploads"))


class Base(DeclarativeBase):
    pass


engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


# SQLite only enforces foreign keys when each connection asks for it.
@event.listens_for(engine, "connect")
def enable_foreign_keys(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
