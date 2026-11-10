from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Course, Source
from app.schemas import CourseIn, CourseOut
from app.services.ingest import source_path


router = APIRouter(prefix="/api/courses", tags=["vakken"])


def get_course(db: Session, course_id: int) -> Course:
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(404, "Vak niet gevonden")
    return course


@router.get("", response_model=list[CourseOut])
def list_courses(db: Session = Depends(get_db)):
    return db.scalars(select(Course).order_by(Course.name)).all()


@router.post("", response_model=CourseOut, status_code=201)
def create_course(payload: CourseIn, db: Session = Depends(get_db)):
    course = Course(**payload.model_dump())
    db.add(course)
    db.commit()
    return course


@router.get("/{course_id}", response_model=CourseOut)
def read_course(course_id: int, db: Session = Depends(get_db)):
    return get_course(db, course_id)


@router.put("/{course_id}", response_model=CourseOut)
def update_course(course_id: int, payload: CourseIn, db: Session = Depends(get_db)):
    course = get_course(db, course_id)
    for key, value in payload.model_dump().items():
        setattr(course, key, value)
    db.commit()
    return course


@router.delete("/{course_id}", status_code=204)
def delete_course(course_id: int, db: Session = Depends(get_db)):
    course = get_course(db, course_id)
    paths = [source_path(source) for source in db.scalars(select(Source).where(Source.course_id == course_id))]
    db.delete(course)
    db.commit()
    for path in paths:
        path.unlink(missing_ok=True)
