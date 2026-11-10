from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Deadline(Base):
    __tablename__ = "deadlines"
    __table_args__ = (UniqueConstraint("course_id", "ical_uid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # UTC
    kind: Mapped[str] = mapped_column(String, nullable=False, default="assignment")  # assignment | exam
    origin: Mapped[str] = mapped_column(String, nullable=False, default="manual")  # manual | ical

    # Lets a re-fetched feed update an event instead of duplicating it.
    ical_uid: Mapped[str | None] = mapped_column(String)

    # A deleted feed event is kept as ignored, so the next sync does not bring it back.
    ignored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
