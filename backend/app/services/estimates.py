"""First estimate: your own rough guess, otherwise base pace x size.

Calibration (correction factor per type and course) comes on top of this later.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Section, Source, Task, TaskRate


def rates_by_type(db: Session) -> dict[str, TaskRate]:
    return {rate.task_type: rate for rate in db.scalars(select(TaskRate))}


def base_estimate_s(task: Task, rate: TaskRate | None) -> int | None:
    if task.manual_estimate_s is not None:
        return task.manual_estimate_s
    if rate is None:
        return None
    return round(task.amount * rate.seconds_per_unit)


def needs_manual_estimate(db: Session, task: Task) -> bool:
    """Tasks from a scanned PDF have no reliable size until you estimate them."""
    if task.manual_estimate_s is not None or task.section_id is None:
        return False
    scanned = db.scalar(
        select(Source.scanned).join(Section, Section.source_id == Source.id).where(Section.id == task.section_id)
    )
    return bool(scanned)


def task_out(db: Session, task: Task, rates: dict[str, TaskRate] | None = None) -> dict:
    rates = rates if rates is not None else rates_by_type(db)
    rate = rates.get(task.task_type)
    manual = needs_manual_estimate(db, task)
    return {
        "id": task.id,
        "course_id": task.course_id,
        "section_id": task.section_id,
        "deadline_id": task.deadline_id,
        "title": task.title,
        "task_type": task.task_type,
        "amount": task.amount,
        "unit": rate.unit if rate else "item",
        "manual_estimate_s": task.manual_estimate_s,
        "estimate_at_start_s": task.estimate_at_start_s,
        "estimate_s": None if manual else base_estimate_s(task, rate),
        "needs_manual_estimate": manual,
        "status": task.status,
    }
