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
