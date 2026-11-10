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
from app.models import Section, Source, StudySession, Task
from app.services.pdf_structure import ExtractedStructure, extract_structure
from app.services.task_builder import build_tasks


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

    store_structure(db, source, structure)

    final_path = source_path(source)
    shutil.move(temporary_path, final_path)
    try:
        db.commit()
    except Exception:
        final_path.unlink(missing_ok=True)
        raise
    return source


def store_structure(db: Session, source: Source, structure: ExtractedStructure) -> None:
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


    for spec in build_tasks(structure.sections):
        db.add(Task(
            course_id=source.course_id, section_id=section_ids[spec.section_index],
            title=spec.title, task_type=spec.task_type, amount=spec.amount,
        ))


def reprocess(db: Session, source: Source) -> Source:
    """Rebuild sections and tasks from the stored file, e.g. after the
    recognition improved. Refused once time is logged on its tasks."""
    tasks = source_tasks(db, source.id)
    if any(db.scalar(select(StudySession.id).where(StudySession.task_id == task.id).limit(1)) for task in tasks):
        raise UploadError("Er is al tijd gelogd op taken van deze bron; opnieuw verwerken zou die wissen")

    structure = extract_structure(source_path(source))
    for task in tasks:
        db.delete(task)
    for section in db.scalars(select(Section).where(Section.source_id == source.id, Section.parent_id.is_(None))):
        db.delete(section)  # children follow through ON DELETE CASCADE
    db.flush()

    source.page_count = structure.page_count
    source.scanned = structure.scanned
    source.structure_method = structure.method
    store_structure(db, source, structure)
    db.commit()
    return source


def source_tasks(db: Session, source_id: int) -> list[Task]:
    return list(db.scalars(
        select(Task).join(Section, Task.section_id == Section.id).where(Section.source_id == source_id)
    ))
