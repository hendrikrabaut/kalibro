from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Deadline, Task
from app.routes.courses import get_course
from app.schemas import TaskCreate, TaskOut, TaskUpdate
from app.services.task_view import task_view, task_views
from app.timeutil import now_utc


router = APIRouter(tags=["taken"])


@router.get("/api/courses/{course_id}/tasks", response_model=list[TaskOut])
def list_tasks(course_id: int, db: Session = Depends(get_db)):
    get_course(db, course_id)
    tasks = db.scalars(select(Task).where(Task.course_id == course_id).order_by(Task.id)).all()
    return task_views(db, list(tasks))


def _check_deadline(db: Session, deadline_id: int | None, course_id: int):
    if deadline_id is None:
        return
    deadline = db.get(Deadline, deadline_id)
    if deadline is None or deadline.course_id != course_id:
        raise HTTPException(400, "Deadline hoort niet bij dit vak")


@router.post("/api/courses/{course_id}/tasks", response_model=TaskOut, status_code=201)
def create_task(course_id: int, payload: TaskCreate, db: Session = Depends(get_db)):
    """A task that is not in any PDF: a lab, a project, revision."""
    get_course(db, course_id)
    _check_deadline(db, payload.deadline_id, course_id)
    task = Task(course_id=course_id, **payload.model_dump())
    db.add(task)
    db.commit()
    return task_view(db, task)


@router.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(404, "Taak niet gevonden")
    db.delete(task)
    db.commit()


@router.patch("/api/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(404, "Taak niet gevonden")
    changes = payload.model_dump(exclude_unset=True)
    _check_deadline(db, changes.get("deadline_id"), task.course_id)
    previous_status = task.status
    for key, value in changes.items():
        setattr(task, key, value)
    if task.status != previous_status:
        task.completed_at = now_utc() if task.status == "done" else None
    db.commit()
    return task_view(db, task)
