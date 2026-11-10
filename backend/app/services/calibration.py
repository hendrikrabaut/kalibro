"""Learn how far off the base estimates are, from your own logged time.

Per finished task: ratio = actual time / base estimate (rate x amount, or your
own estimate). Ratios are averaged in log space, so 2x too slow and 2x too fast
cancel out. With little data the average is pulled towards the level above:

    course+type  ->  type  ->  all tasks  ->  1.0 (the base estimate as is)

Each level counts as PRIOR_WEIGHT tasks of evidence for the one below, so one
weird task cannot swing the factor, and ten consistent ones clearly do.

The spread of the ratios gives the margin. It starts at PRIOR_SIGMA and narrows
as the estimates get better.
"""

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StudySession, Task, TaskRate, WeeklyAccuracy
from app.services.estimates import base_estimate_s, rates_by_type
from app.timeutil import now_utc


PRIOR_WEIGHT = 3.0
PRIOR_SIGMA = 0.35  # log space: roughly x0.64 to x1.56 for the 80% margin at the start
INTERVAL_Z = 1.2816  # 80% interval


@dataclass
class Factor:
    factor: float  # multiply the base estimate by this
    log_mean: float
    sigma: float
    sample_size: int  # finished tasks behind this exact level

    def margin(self, estimate_s: float) -> tuple[int, int]:
        spread = math.exp(INTERVAL_Z * self.sigma)
        return round(estimate_s / spread), round(estimate_s * spread)


def logged_seconds(db: Session, task_ids: list[int] | None = None) -> dict[int, int]:
    """Logged time per task; a running timer counts up to now."""
    query = select(StudySession.task_id, StudySession.start_at, StudySession.end_at)
    if task_ids is not None:
        query = query.where(StudySession.task_id.in_(task_ids))
    now = now_utc()
    totals: dict[int, int] = defaultdict(int)
    for task_id, start, end in db.execute(query):
        totals[task_id] += max(0, int(((end or now) - start).total_seconds()))
    return totals


@dataclass
class Observation:
    task: Task
    actual_s: int
    log_ratio: float


def observations(db: Session, rates: dict[str, TaskRate]) -> list[Observation]:
    done = list(db.scalars(select(Task).where(Task.status == "done")))
    logged = logged_seconds(db, [task.id for task in done])
    result = []
    for task in done:
        base = base_estimate_s(task, rates.get(task.task_type))
        actual = logged.get(task.id, 0)
        # Without logged time there is nothing to learn from.
        if base and actual > 0:
            result.append(Observation(task, actual, math.log(actual / base)))
    return result


class Calibrator:
    def __init__(self, db: Session):
        self.rates = rates_by_type(db)
        self.observations = observations(db, self.rates)

        logs_all = [o.log_ratio for o in self.observations]
        by_type: dict[str, list[float]] = defaultdict(list)
        by_course_type: dict[tuple[int, str], list[float]] = defaultdict(list)
        for o in self.observations:
            by_type[o.task.task_type].append(o.log_ratio)
            by_course_type[(o.task.course_id, o.task.task_type)].append(o.log_ratio)

        self.global_mean = _shrink(logs_all, 0.0)
        self.type_means = {t: _shrink(v, self.global_mean) for t, v in by_type.items()}
        self.course_type = by_course_type
        self.by_type = by_type

        # One pooled spread: per level there is rarely enough data for its own.
        residuals = [
            o.log_ratio - self._mean(o.task.course_id, o.task.task_type) for o in self.observations
        ]
        self.sigma = math.sqrt(
            (sum(r * r for r in residuals) + PRIOR_WEIGHT * PRIOR_SIGMA**2) / (len(residuals) + PRIOR_WEIGHT)
        )

    def _mean(self, course_id: int, task_type: str) -> float:
        type_mean = self.type_means.get(task_type, self.global_mean)
        return _shrink(self.course_type.get((course_id, task_type), []), type_mean)

    def factor(self, course_id: int, task_type: str) -> Factor:
        log_mean = self._mean(course_id, task_type)
        return Factor(
            factor=math.exp(log_mean),
            log_mean=log_mean,
            sigma=self.sigma,
            sample_size=len(self.course_type.get((course_id, task_type), [])),
        )

    def estimate_s(self, task: Task) -> int | None:
        base = base_estimate_s(task, self.rates.get(task.task_type))
        if base is None:
            return None
        return round(base * self.factor(task.course_id, task.task_type).factor)


def _shrink(values: list[float], prior: float) -> float:
    return (sum(values) + PRIOR_WEIGHT * prior) / (len(values) + PRIOR_WEIGHT)


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def weekly_accuracy(db: Session) -> list[dict]:
    """MAPE per week of completion, against the estimate frozen at the start.

    Finished weeks are written to weekly_accuracy, so the history stays even if
    sessions are edited later; the current week is always computed live."""
    done = list(db.scalars(
        select(Task).where(Task.status == "done", Task.completed_at.is_not(None), Task.estimate_at_start_s.is_not(None))
    ))
    logged = logged_seconds(db, [task.id for task in done])
    errors: dict[date, list[float]] = defaultdict(list)
    for task in done:
        actual = logged.get(task.id, 0)
        if actual > 0:
            errors[week_start(task.completed_at.date())].append(abs(actual - task.estimate_at_start_s) / actual)

    current = week_start(now_utc().date())
    stored = {row.week_start: row for row in db.scalars(select(WeeklyAccuracy))}
    for week, values in errors.items():
        if week < current and week not in stored:
            row = WeeklyAccuracy(week_start=week, task_count=len(values), mape=100 * sum(values) / len(values))
            db.add(row)
            stored[week] = row
    db.commit()

    weeks = [
        {"week_start": row.week_start, "task_count": row.task_count, "mape": round(row.mape, 1)}
        for row in stored.values()
    ]
    if current in errors:
        values = errors[current]
        weeks.append({"week_start": current, "task_count": len(values), "mape": round(100 * sum(values) / len(values), 1), "live": True})
    return sorted(weeks, key=lambda week: week["week_start"])
