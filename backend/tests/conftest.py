import os
import tempfile
from pathlib import Path

# Must be set before anything imports app.database, so tests never touch real data.
_directory = tempfile.TemporaryDirectory()
os.environ["KALIBRO_DB"] = str(Path(_directory.name) / "test.db")
os.environ["KALIBRO_UPLOADS"] = str(Path(_directory.name) / "uploads")

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import engine
from app.main import app


BACKEND = Path(__file__).resolve().parents[1]

# Children first, so foreign keys never block the cleanup.
TABLES = (
    "study_sessions",
    "plan_blocks",
    "plan_versions",
    "tasks",
    "sections",
    "sources",
    "deadlines",
    "availability_exceptions",
    "availability_slots",
    "weekly_accuracy",
    "courses",
)


@pytest.fixture(scope="session", autouse=True)
def schema():
    command.upgrade(Config(BACKEND / "alembic.ini"), "head")


@pytest.fixture(autouse=True)
def clean_tables(schema):
    with engine.begin() as connection:
        for table in TABLES:
            connection.execute(text(f"DELETE FROM {table}"))


@pytest.fixture
def client():
    return TestClient(app)
