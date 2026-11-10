from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Course(Base):
    """A vak."""

    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    color: Mapped[str | None] = mapped_column(String)
    credits: Mapped[float | None] = mapped_column(Float)

    # iCal feed of the learning platform; deadlines are pulled from it.
    ical_url: Mapped[str | None] = mapped_column(String)
