"""Start/stop timer. At most one session runs at a time: starting another task
stops the running one, so switching on the small screen is one tap."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StudySession, Task
from app.services.calibration import Calibrator
from app.timeutil import now_utc


def running_session(db: Session) -> StudySession | None:
    return db.scalar(select(StudySession).where(StudySession.end_at.is_(None)).limit(1))


def stop(db: Session, at: datetime | None = None) -> StudySession | None:
    session = running_session(db)
    if session is not None:
        session.end_at = max(at or now_utc(), session.start_at)
    return session


def freeze_estimate(db: Session, task: Task) -> None:
    """The estimate as it stood before any work: what the MAPE is measured on."""
    if task.estimate_at_start_s is None:
        task.estimate_at_start_s = Calibrator(db).estimate_s(task)


def start(db: Session, task: Task) -> StudySession:
    current = running_session(db)
    if current is not None and current.task_id == task.id:
        return current
    now = now_utc()
    stop(db, now)
    freeze_estimate(db, task)
    if task.status == "open":
        task.status = "in_progress"
    session = StudySession(task_id=task.id, start_at=now)
    db.add(session)
    db.commit()
    return session


def complete(db: Session, task: Task) -> None:
    current = running_session(db)
    if current is not None and current.task_id == task.id:
        stop(db)
    task.status = "done"
    task.completed_at = now_utc()
    db.commit()
