"""Put the remaining work into the free study blocks.

- Free time: the weekly pattern plus the exceptions per date, in local time.
- Order: earliest deadline first (EDF), and within one deadline the order of the
  material. EDF is the order that keeps the worst lateness as small as possible.
- A task can be spread over several blocks, but never in pieces shorter than
  MIN_BLOCK_S, unless that finishes the task.
- Remaining work = calibrated estimate - logged time, so replanning after
  falling behind needs no special case: it is just planning again.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import LOCAL_TZ
from app.models import (
    AvailabilityException, AvailabilitySlot, Deadline, PlanBlock, PlanVersion, Section, Task,
)
from app.services.calibration import Calibrator
from app.services.task_view import task_views
from app.timeutil import now_utc, utc_naive


MIN_BLOCK_S = 25 * 60
DEFAULT_HORIZON = timedelta(weeks=8)
MAX_HORIZON = timedelta(weeks=26)

Interval = tuple[datetime, datetime]  # naive UTC


# ---------------------------------------------------------------- free time

def _local_to_utc(day: date, clock: str) -> datetime:
    hours, minutes = map(int, clock.split(":"))
    return utc_naive(datetime.combine(day, time(hours, minutes), tzinfo=LOCAL_TZ))


def _subtract(intervals: list[Interval], cut: Interval) -> list[Interval]:
    result = []
    for start, end in intervals:
        if cut[1] <= start or cut[0] >= end:
            result.append((start, end))
            continue
        if start < cut[0]:
            result.append((start, cut[0]))
        if cut[1] < end:
            result.append((cut[1], end))
    return result


def _merge(intervals: list[Interval]) -> list[Interval]:
    merged: list[Interval] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def free_intervals(db: Session, start: datetime, end: datetime) -> list[Interval]:
    slots: dict[int, list[AvailabilitySlot]] = defaultdict(list)
    for slot in db.scalars(select(AvailabilitySlot)):
        slots[slot.weekday].append(slot)

    first_day = (start.replace(tzinfo=None) - timedelta(days=1)).date()
    last_day = (end + timedelta(days=1)).date()
    exceptions: dict[date, list[AvailabilityException]] = defaultdict(list)
    for exception in db.scalars(
        select(AvailabilityException).where(
            AvailabilityException.day >= first_day, AvailabilityException.day <= last_day
        )
    ):
        exceptions[exception.day].append(exception)

    intervals: list[Interval] = []
    day = first_day
    while day <= last_day:
        todays = [(_local_to_utc(day, s.start_time), _local_to_utc(day, s.end_time)) for s in slots[day.weekday()]]
        for exception in exceptions[day]:
            if exception.available:
                todays.append((_local_to_utc(day, exception.start_time), _local_to_utc(day, exception.end_time)))
            elif exception.start_time is None:
                todays = []  # the whole day is gone
            else:
                todays = _subtract(
                    todays, (_local_to_utc(day, exception.start_time), _local_to_utc(day, exception.end_time))
                )
        intervals.extend(todays)
        day += timedelta(days=1)

    clipped = [(max(s, start), min(e, end)) for s, e in intervals]
    return _merge([(s, e) for s, e in clipped if e > s])


def capacity_s(intervals: list[Interval], until: datetime) -> int:
    return int(sum(max(0.0, (min(e, until) - s).total_seconds()) for s, e in intervals if s < until))


# ---------------------------------------------------------------- scheduling

@dataclass
class WorkItem:
    task_id: int
    remaining_s: int
    due_at: datetime | None
    order: tuple  # tie-break: course, position in the material


@dataclass
class Schedule:
    blocks: list[tuple[int, datetime, datetime]] = field(default_factory=list)  # task, start, end
    unscheduled_s: dict[int, int] = field(default_factory=dict)  # no room left before the horizon
    finish: dict[int, datetime] = field(default_factory=dict)


def schedule(intervals: list[Interval], items: list[WorkItem]) -> Schedule:
    far = datetime.max
    queue = sorted(items, key=lambda item: (item.due_at or far, item.order))
    free = [list(interval) for interval in intervals]
    result = Schedule()
    slot = 0

    for item in queue:
        left = item.remaining_s
        while left > 0 and slot < len(free):
            start, end = free[slot]
            available = int((end - start).total_seconds())
            # Too short for a useful piece, unless it finishes the task.
            if available < min(MIN_BLOCK_S, left):
                slot += 1
                continue
            used = min(available, left)
            # Do not leave a leftover piece shorter than the minimum.
            if 0 < left - used < MIN_BLOCK_S and used - (MIN_BLOCK_S - (left - used)) >= MIN_BLOCK_S:
                used -= MIN_BLOCK_S - (left - used)
            block_end = start + timedelta(seconds=used)
            result.blocks.append((item.task_id, start, block_end))
            result.finish[item.task_id] = block_end
            left -= used
            free[slot][0] = block_end
            if block_end >= end:
                slot += 1
        if left > 0:
            result.unscheduled_s[item.task_id] = left
    return result


# ---------------------------------------------------------------- planning

def _open_tasks(db: Session) -> list[tuple[Task, int | None]]:
    """Unfinished tasks with their order in the material."""
    rows = db.execute(
        select(Task, Section.source_id, Section.position)
        .outerjoin(Section, Task.section_id == Section.id)
        .where(Task.status != "done")
    ).all()
    return [(task, (source_id or 0, position or 0, task.id)) for task, source_id, position in rows]


@dataclass
class PlanInput:
    now: datetime
    horizon: datetime
    intervals: list[Interval]
    items: list[WorkItem]
    high_s: dict[int, int]  # remaining work if the high end of the margin comes true
    views: dict[int, dict]
    deadlines: dict[int, Deadline]
    needs_estimate: list[dict]


def gather(db: Session, now: datetime | None = None) -> PlanInput:
    now = now or now_utc()
    rows = _open_tasks(db)
    calibrator = Calibrator(db)
    views = {view["id"]: view for view in task_views(db, [task for task, _ in rows], calibrator)}
    deadlines = {d.id: d for d in db.scalars(select(Deadline))}

    items, high, needs_estimate = [], {}, []
    for task, order in rows:
        view = views[task.id]
        if view["remaining_s"] is None:
            needs_estimate.append(view)
            continue
        deadline = deadlines.get(task.deadline_id)
        items.append(WorkItem(task.id, view["remaining_s"], deadline.due_at if deadline else None, (task.course_id, *order)))
        high[task.id] = max(view["estimate_high_s"] - view["logged_s"], view["remaining_s"])

    future_deadlines = [d.due_at for d in deadlines.values() if d.due_at > now]
    horizon = max([now + DEFAULT_HORIZON, *future_deadlines])
    horizon = min(horizon, now + MAX_HORIZON)
    return PlanInput(
        now=now, horizon=horizon, intervals=free_intervals(db, now, horizon), items=items,
        high_s=high, views=views, deadlines=deadlines, needs_estimate=needs_estimate,
    )


def feasibility(plan_input: PlanInput) -> list[dict]:
    """Per upcoming deadline: is all work due by then possible in the free time?"""
    result = []
    for deadline in sorted(plan_input.deadlines.values(), key=lambda d: d.due_at):
        if deadline.due_at <= plan_input.now:
            continue
        due = [item for item in plan_input.items if item.due_at is not None and item.due_at <= deadline.due_at]
        own = [item for item in due if plan_input.views[item.task_id]["deadline_id"] == deadline.id]
        if not own:
            continue
        work = sum(item.remaining_s for item in due)
        work_high = sum(plan_input.high_s[item.task_id] for item in due)
        capacity = capacity_s(plan_input.intervals, deadline.due_at)
        status = "ok" if work_high <= capacity else "tight" if work <= capacity else "infeasible"
        result.append({
            "deadline_id": deadline.id,
            "course_id": deadline.course_id,
            "title": deadline.title,
            "due_at": deadline.due_at,
            "work_s": work,
            "work_high_s": work_high,
            "capacity_s": capacity,
            "slack_s": capacity - work,
            "status": status,
        })
    return result


def make_plan(db: Session, reason: str | None = None, now: datetime | None = None) -> PlanVersion:
    plan_input = gather(db, now)
    result = schedule(plan_input.intervals, plan_input.items)
    version = PlanVersion(created_at=plan_input.now, reason=reason)
    db.add(version)
    db.flush()
    for task_id, start, end in result.blocks:
        db.add(PlanBlock(plan_version_id=version.id, task_id=task_id, start_at=start, end_at=end))
    db.commit()
    return version


def latest_version(db: Session) -> PlanVersion | None:
    return db.scalar(select(PlanVersion).order_by(PlanVersion.id.desc()).limit(1))


def plan_overview(db: Session, now: datetime | None = None) -> dict:
    """The latest plan with a live check: what is late, what did not fit."""
    plan_input = gather(db, now)
    version = latest_version(db)
    blocks = []
    if version is not None:
        blocks = list(db.scalars(
            select(PlanBlock).where(PlanBlock.plan_version_id == version.id).order_by(PlanBlock.start_at)
        ))

    # Recomputed from the current state, so it shows the effect of falling behind
    # even before you replan.
    fresh = schedule(plan_input.intervals, plan_input.items)
    late = []
    for item in plan_input.items:
        finish = fresh.finish.get(item.task_id)
        if item.due_at is not None and (item.task_id in fresh.unscheduled_s or (finish and finish > item.due_at)):
            late.append({"task_id": item.task_id, "title": plan_input.views[item.task_id]["title"], "due_at": item.due_at})

    titles = {task_id: view["title"] for task_id, view in plan_input.views.items()}
    courses = {task_id: view["course_id"] for task_id, view in plan_input.views.items()}
    return {
        "version": version,
        "blocks": [
            {
                "task_id": block.task_id,
                "title": titles.get(block.task_id) or db.get(Task, block.task_id).title,
                "course_id": courses.get(block.task_id) or db.get(Task, block.task_id).course_id,
                "start_at": block.start_at,
                "end_at": block.end_at,
                "done": block.task_id not in titles,
            }
            for block in blocks
        ],
        "deadlines": feasibility(plan_input),
        "late_tasks": late,
        "unscheduled": [
            {"task_id": task_id, "title": titles[task_id], "remaining_s": seconds}
            for task_id, seconds in fresh.unscheduled_s.items()
        ],
        "needs_estimate": [{"task_id": view["id"], "title": view["title"]} for view in plan_input.needs_estimate],
        "horizon": plan_input.horizon,
        "free_s": capacity_s(plan_input.intervals, plan_input.horizon),
        "work_s": sum(item.remaining_s for item in plan_input.items),
    }
