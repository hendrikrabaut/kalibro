from datetime import date

from sqlalchemy import Boolean, Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AvailabilitySlot(Base):
    """A recurring weekly study block, in local time."""

    __tablename__ = "availability_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0 = Monday
    start_time: Mapped[str] = mapped_column(String, nullable=False)  # "HH:MM"
    end_time: Mapped[str] = mapped_column(String, nullable=False)


class AvailabilityException(Base):
    """A one-off change on a date: a day off, or an extra block."""

    __tablename__ = "availability_exceptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Unavailable with no times = the whole day is gone.
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    start_time: Mapped[str | None] = mapped_column(String)
    end_time: Mapped[str | None] = mapped_column(String)
    note: Mapped[str | None] = mapped_column(String)
