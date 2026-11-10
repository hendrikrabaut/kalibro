from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Deadline, Task
from app.routes.courses import get_course
from app.schemas import TaskOut, TaskUpdate
from app.services.estimates import rates_by_type, task_out


router = APIRouter(tags=["taken"])


@router.get("/api/courses/{course_id}/tasks", response_model=list[TaskOut])
def list_tasks(course_id: int, db: Session = Depends(get_db)):
    get_course(db, course_id)
    rates = rates_by_type(db)
    tasks = db.scalars(select(Task).where(Task.course_id == course_id).order_by(Task.id)).all()
    return [task_out(db, task, rates) for task in tasks]


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
    db.commit()
    return task_out(db, task)
