from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


TASK_TYPES = ("reading", "slides", "exercises", "lab", "review", "other")
TASK_STATUSES = ("open", "in_progress", "done")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_id: Mapped[int | None] = mapped_column(
        ForeignKey("sections.id", ondelete="SET NULL"), index=True
    )
    deadline_id: Mapped[int | None] = mapped_column(
        ForeignKey("deadlines.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    task_type: Mapped[str] = mapped_column(String, nullable=False)

    # Size in the unit of the task type's rate (pages, slides, exercises, ...).
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    # The user's own rough estimate; overrides rate x amount when set.
    manual_estimate_s: Mapped[int | None] = mapped_column(Integer)

    # Frozen when the first session starts, so later recalibration cannot
    # rewrite history and the weekly error stays an honest measurement.
    estimate_at_start_s: Mapped[int | None] = mapped_column(Integer)

    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
