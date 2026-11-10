from datetime import date

from sqlalchemy import Date, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TaskRate(Base):
    """Base pace per task type, before calibration."""

    __tablename__ = "task_rates"

    task_type: Mapped[str] = mapped_column(String, primary_key=True)
    unit: Mapped[str] = mapped_column(String, nullable=False)  # page | slide | exercise | item
    seconds_per_unit: Mapped[float] = mapped_column(Float, nullable=False)


class WeeklyAccuracy(Base):
    """Snapshot of estimation error per week. Correction factors themselves are
    computed from the sessions and not stored; only this trend is kept."""

    __tablename__ = "weekly_accuracy"

    week_start: Mapped[date] = mapped_column(Date, primary_key=True)  # Monday
    task_count: Mapped[int] = mapped_column(Integer, nullable=False)
    mape: Mapped[float] = mapped_column(Float, nullable=False)
