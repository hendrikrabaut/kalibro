from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Source(Base):
    """An uploaded file (PDF, later PPTX). The file itself sits in UPLOAD_DIR."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)  # pdf | pptx
    sha256: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # No text layer: no OCR in v1, so its tasks need a manual estimate.
    scanned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # toc | fonts | slides | none: how the structure was found.
    structure_method: Mapped[str] = mapped_column(String, nullable=False, default="none")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
