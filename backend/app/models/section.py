from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Section(Base):
    """An onderdeel: a node in the table of contents of a source."""

    __tablename__ = "sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("sections.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 = top
    position: Mapped[int] = mapped_column(Integer, nullable=False)  # order within the source

    # Pages are 1-based and inclusive. Counts cover the section without its children.
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    slide_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    exercise_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
