from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Deadline, Task
from app.routes.courses import get_course
from app.schemas import DeadlineIn, DeadlineOut
from app.services.deadline_sync import sync_course
from app.timeutil import utc_naive


router = APIRouter(tags=["deadlines"])


@router.get("/api/deadlines", response_model=list[DeadlineOut])
def list_all_deadlines(db: Session = Depends(get_db)):
    return db.scalars(select(Deadline).where(Deadline.ignored.is_(False)).order_by(Deadline.due_at)).all()


@router.get("/api/courses/{course_id}/deadlines", response_model=list[DeadlineOut])
def list_deadlines(course_id: int, db: Session = Depends(get_db)):
    get_course(db, course_id)
    return db.scalars(select(Deadline).where(Deadline.course_id == course_id, Deadline.ignored.is_(False)).order_by(Deadline.due_at)).all()


@router.post("/api/courses/{course_id}/deadlines", response_model=DeadlineOut, status_code=201)
def create_deadline(course_id: int, payload: DeadlineIn, db: Session = Depends(get_db)):
    get_course(db, course_id)
    deadline = Deadline(
        course_id=course_id, title=payload.title, due_at=utc_naive(payload.due_at), kind=payload.kind,
    )
    db.add(deadline)
    db.commit()
    return deadline


def get_deadline(db: Session, deadline_id: int) -> Deadline:
    deadline = db.get(Deadline, deadline_id)
    if deadline is None:
        raise HTTPException(404, "Deadline niet gevonden")
    return deadline


@router.put("/api/deadlines/{deadline_id}", response_model=DeadlineOut)
def update_deadline(deadline_id: int, payload: DeadlineIn, db: Session = Depends(get_db)):
    deadline = get_deadline(db, deadline_id)
    deadline.title = payload.title
    deadline.due_at = utc_naive(payload.due_at)
    deadline.kind = payload.kind
    db.commit()
    return deadline


@router.delete("/api/deadlines/{deadline_id}", status_code=204)
def delete_deadline(deadline_id: int, db: Session = Depends(get_db)):
    deadline = get_deadline(db, deadline_id)
    if deadline.origin == "ical":
        # Kept as ignored, otherwise the next sync would add it again.
        deadline.ignored = True
        for task in db.scalars(select(Task).where(Task.deadline_id == deadline.id)):
            task.deadline_id = None
    else:
        db.delete(deadline)
    db.commit()


@router.post("/api/courses/{course_id}/deadlines/sync")
def sync_deadlines(course_id: int, db: Session = Depends(get_db)):
    course = get_course(db, course_id)
    try:
        return sync_course(db, course)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    except OSError as error:  # network errors, HTTP errors, timeouts
        raise HTTPException(502, f"Kon de feed niet ophalen: {error}") from error
