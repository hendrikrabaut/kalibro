"""Store an uploaded PDF, extract its structure and create tasks from it."""

import hashlib
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import database
from app.models import Section, Source, Task
from app.services.pdf_structure import extract_structure


CHUNK_SIZE = 1024 * 1024
MAX_UPLOAD_BYTES = 200 * 1024 * 1024


class UploadError(ValueError):
    pass


class DuplicateSource(UploadError):
    def __init__(self, existing: Source):
        super().__init__(f"Dit bestand is al geüpload als '{existing.filename}'")
        self.existing = existing


def source_path(source: Source) -> Path:
    return database.UPLOAD_DIR / f"{source.sha256}.{source.kind}"


def ingest_pdf(db: Session, course_id: int, filename: str, stream: BinaryIO) -> Source:
    database.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # Write in chunks while hashing, so a large PDF never sits in memory at once.
    digest = hashlib.sha256()
    size = 0
    with tempfile.NamedTemporaryFile(dir=database.UPLOAD_DIR, suffix=".part", delete=False) as temporary:
        temporary_path = Path(temporary.name)
        first = stream.read(CHUNK_SIZE)
        if not first.startswith(b"%PDF"):
            temporary.close()
            temporary_path.unlink()
            raise UploadError("Dit is geen PDF-bestand")
        chunk = first
        while chunk:
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                temporary.close()
                temporary_path.unlink()
                raise UploadError("Bestand is groter dan 200 MB")
            digest.update(chunk)
            temporary.write(chunk)
            chunk = stream.read(CHUNK_SIZE)

    sha256 = digest.hexdigest()
    existing = db.scalar(select(Source).where(Source.sha256 == sha256))
    if existing is not None:
        temporary_path.unlink()
        raise DuplicateSource(existing)

    try:
        structure = extract_structure(temporary_path)
    except Exception as error:  # PyMuPDF raises several types for broken files
        temporary_path.unlink()
        raise UploadError("Kon de PDF niet lezen") from error

    source = Source(
        course_id=course_id,
        filename=Path(filename).name or "bestand.pdf",
        kind="pdf",
        sha256=sha256,
        page_count=structure.page_count,
        scanned=structure.scanned,
        structure_method=structure.method,
        uploaded_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(source)
    db.flush()

    section_ids: list[int] = []
    for position, extracted in enumerate(structure.sections):
        section = Section(
            source_id=source.id,
            parent_id=section_ids[extracted.parent_index] if extracted.parent_index is not None else None,
            title=extracted.title,
            level=extracted.level,
            position=position,
            page_start=extracted.page_start,
            page_end=extracted.page_end,
            word_count=extracted.word_count,
            exercise_count=extracted.exercise_count,
        )
        db.add(section)
        db.flush()
        section_ids.append(section.id)

        # A heading with no pages of its own (its children cover them) needs no task.
        if extracted.own_pages:
            db.add(Task(
                course_id=course_id, section_id=section.id, title=extracted.title,
                task_type="reading", amount=extracted.own_pages,
            ))
        if extracted.exercise_count:
            db.add(Task(
                course_id=course_id, section_id=section.id, title=f"{extracted.title}: oefeningen",
                task_type="exercises", amount=extracted.exercise_count,
            ))

    final_path = source_path(source)
    shutil.move(temporary_path, final_path)
    try:
        db.commit()
    except Exception:
        final_path.unlink(missing_ok=True)
        raise
    return source
