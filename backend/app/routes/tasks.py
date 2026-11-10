from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Deadline, Task
from app.routes.courses import get_course
from app.schemas import TaskOut, TaskUpdate
from app.services.task_view import task_view, task_views
from app.timeutil import now_utc


router = APIRouter(tags=["taken"])


@router.get("/api/courses/{course_id}/tasks", response_model=list[TaskOut])
def list_tasks(course_id: int, db: Session = Depends(get_db)):
    get_course(db, course_id)
    tasks = db.scalars(select(Task).where(Task.course_id == course_id).order_by(Task.id)).all()
    return task_views(db, list(tasks))


@router.patch("/api/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(404, "Taak niet gevonden")
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("deadline_id") is not None:
        deadline = db.get(Deadline, changes["deadline_id"])
        if deadline is None or deadline.course_id != task.course_id:
            raise HTTPException(400, "Deadline hoort niet bij dit vak")
    for key, value in changes.items():
        setattr(task, key, value)
    if "status" in changes:
        task.completed_at = now_utc() if task.status == "done" else None
    db.commit()
    return task_view(db, task)
