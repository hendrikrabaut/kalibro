from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import StudySession, Task
from app.schemas import SessionIn, SessionOut, TaskOut, TimerOut
from app.services import timer
from app.services.task_view import task_view
from app.timeutil import now_utc, utc_naive


router = APIRouter(tags=["timer"])


def get_task(db: Session, task_id: int) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(404, "Taak niet gevonden")
    return task


def timer_state(db: Session) -> dict:
    session = timer.running_session(db)
    if session is None:
        return {"running": False}
    return {
        "running": True,
        "session": session,
        "task": task_view(db, db.get(Task, session.task_id)),
        "elapsed_s": int((now_utc() - session.start_at).total_seconds()),
    }


@router.get("/api/timer", response_model=TimerOut)
def read_timer(db: Session = Depends(get_db)):
    return timer_state(db)


@router.post("/api/tasks/{task_id}/start", response_model=TimerOut)
def start_timer(task_id: int, db: Session = Depends(get_db)):
    task = get_task(db, task_id)
    if task.status == "done":
        raise HTTPException(409, "Deze taak is al af; zet ze eerst terug op open")
    timer.start(db, task)
    return timer_state(db)


@router.post("/api/timer/stop", response_model=TimerOut)
def stop_timer(db: Session = Depends(get_db)):
    timer.stop(db)
    db.commit()
    return timer_state(db)


@router.post("/api/tasks/{task_id}/complete", response_model=TaskOut)
def complete_task(task_id: int, db: Session = Depends(get_db)):
    task = get_task(db, task_id)
    timer.complete(db, task)
    return task_view(db, task)


@router.get("/api/tasks/{task_id}/sessions", response_model=list[SessionOut])
def list_sessions(task_id: int, db: Session = Depends(get_db)):
    get_task(db, task_id)
    return db.scalars(select(StudySession).where(StudySession.task_id == task_id).order_by(StudySession.start_at)).all()


@router.post("/api/tasks/{task_id}/sessions", response_model=SessionOut, status_code=201)
def add_session(task_id: int, payload: SessionIn, db: Session = Depends(get_db)):
    task = get_task(db, task_id)
    start, end = utc_naive(payload.start_at), utc_naive(payload.end_at)
    if end <= start:
        raise HTTPException(422, "Het einde moet na het begin liggen")
    if end > now_utc():
        raise HTTPException(422, "Een sessie kan niet in de toekomst eindigen")
    timer.freeze_estimate(db, task)
    if task.status == "open":
        task.status = "in_progress"
    session = StudySession(task_id=task_id, start_at=start, end_at=end)
    db.add(session)
    db.commit()
    return session


@router.delete("/api/sessions/{session_id}", status_code=204)
def delete_session(session_id: int, db: Session = Depends(get_db)):
    session = db.get(StudySession, session_id)
    if session is None:
        raise HTTPException(404, "Sessie niet gevonden")
    db.delete(session)
    db.commit()
