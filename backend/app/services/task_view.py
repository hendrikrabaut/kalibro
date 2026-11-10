from sqlalchemy.orm import Session

from app.models import Task
from app.services.calibration import Calibrator, logged_seconds
from app.services.estimates import base_estimate_s, needs_manual_estimate


# An unfinished task that ran over its estimate still needs some time.
MIN_REMAINING_S = 15 * 60


def remaining_s(estimate: int | None, logged: int, status: str) -> int | None:
    if status == "done":
        return 0
    if estimate is None:
        return None
    return max(estimate - logged, MIN_REMAINING_S)


def task_views(db: Session, tasks: list[Task], calibrator: Calibrator | None = None) -> list[dict]:
    calibrator = calibrator or Calibrator(db)
    logged = logged_seconds(db, [task.id for task in tasks])
    views = []
    for task in tasks:
        rate = calibrator.rates.get(task.task_type)
        manual = needs_manual_estimate(db, task)
        base = None if manual else base_estimate_s(task, rate)
        factor = calibrator.factor(task.course_id, task.task_type)
        estimate = None if base is None else round(base * factor.factor)
        low, high = factor.margin(estimate) if estimate is not None else (None, None)
        spent = logged.get(task.id, 0)
        views.append({
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
            "base_estimate_s": base,
            "factor": round(factor.factor, 3),
            "estimate_s": estimate,
            "estimate_low_s": low,
            "estimate_high_s": high,
            "logged_s": spent,
            "remaining_s": remaining_s(estimate, spent, task.status),
            "needs_manual_estimate": manual,
            "status": task.status,
        })
    return views


def task_view(db: Session, task: Task) -> dict:
    return task_views(db, [task])[0]
