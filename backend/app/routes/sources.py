from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Section, Source, Task
from app.routes.courses import get_course
from app.schemas import SourceDetail, SourceOut
from app.services.estimates import rates_by_type, task_out
from app.services.ingest import DuplicateSource, UploadError, ingest_pdf, source_path


router = APIRouter(tags=["bronnen"])


def source_detail(db: Session, source: Source) -> dict:
    sections = db.scalars(
        select(Section).where(Section.source_id == source.id).order_by(Section.position)
    ).all()
    tasks = db.scalars(
        select(Task).join(Section, Task.section_id == Section.id)
        .where(Section.source_id == source.id).order_by(Section.position, Task.id)
    ).all()
    rates = rates_by_type(db)
    return {
        **SourceOut.model_validate(source).model_dump(),
        "sections": sections,
        "tasks": [task_out(db, task, rates) for task in tasks],
    }


# Plain def: FastAPI runs it in a thread, so a slow extraction does not block other requests.
@router.post("/api/courses/{course_id}/sources", response_model=SourceDetail, status_code=201)
def upload_source(course_id: int, file: UploadFile, db: Session = Depends(get_db)):
    get_course(db, course_id)
    try:
        source = ingest_pdf(db, course_id, file.filename or "", file.file)
    except DuplicateSource as error:
        raise HTTPException(409, str(error)) from error
    except UploadError as error:
        raise HTTPException(400, str(error)) from error
    return source_detail(db, source)


@router.get("/api/courses/{course_id}/sources", response_model=list[SourceOut])
def list_sources(course_id: int, db: Session = Depends(get_db)):
    get_course(db, course_id)
    return db.scalars(select(Source).where(Source.course_id == course_id).order_by(Source.uploaded_at)).all()


def get_source(db: Session, source_id: int) -> Source:
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(404, "Bron niet gevonden")
    return source


@router.get("/api/sources/{source_id}", response_model=SourceDetail)
def read_source(source_id: int, db: Session = Depends(get_db)):
    return source_detail(db, get_source(db, source_id))


@router.delete("/api/sources/{source_id}", status_code=204)
def delete_source(source_id: int, db: Session = Depends(get_db)):
    source = get_source(db, source_id)
    path = source_path(source)
    # Tasks from this source go too; section_id would otherwise just become NULL.
    for task in db.scalars(
        select(Task).join(Section, Task.section_id == Section.id).where(Section.source_id == source_id)
    ):
        db.delete(task)
    db.delete(source)
    db.commit()
    path.unlink(missing_ok=True)
