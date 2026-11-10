from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PlanVersion(Base):
    """Every (re)plan is a new version, so you can see how the plan shifted."""

    __tablename__ = "plan_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    reason: Mapped[str | None] = mapped_column(String)  # e.g. "achter op schema"


class PlanBlock(Base):
    __tablename__ = "plan_blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_version_id: Mapped[int] = mapped_column(
        ForeignKey("plan_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # UTC
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
