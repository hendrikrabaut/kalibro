from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Course, Deadline, PlanBlock, Task
from app.schemas import PlanRequest
from app.services import planner
from app.services.ical import OutEvent, deadline_event_bounds, write_calendar
from app.timeutil import as_utc


router = APIRouter(tags=["plan"])


def _utc_everywhere(value):
    """Mark every naive (UTC) datetime in the response as UTC."""
    if isinstance(value, datetime):
        return as_utc(value).isoformat()
    if isinstance(value, dict):
        return {key: _utc_everywhere(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_utc_everywhere(item) for item in value]
    return value


def _overview(db: Session) -> dict:
    overview = planner.plan_overview(db)
    version = overview["version"]
    overview["version"] = None if version is None else {
        "id": version.id, "created_at": version.created_at, "reason": version.reason,
    }
    return jsonable_encoder(_utc_everywhere(overview))


@router.get("/api/plan")
def read_plan(db: Session = Depends(get_db)):
    """Latest plan plus a live check against the current state."""
    return _overview(db)


@router.post("/api/plan", status_code=201)
def create_plan(payload: PlanRequest | None = None, db: Session = Depends(get_db)):
    """(Re)plan all remaining work from now on. Old versions are kept."""
    planner.make_plan(db, reason=payload.reason if payload else None)
    return _overview(db)


@router.get("/api/calendar.ics")
def calendar_feed(db: Session = Depends(get_db)):
    """Subscribe to this URL in your calendar app, or download it once."""
    events: list[OutEvent] = []
    courses = {course.id: course.name for course in db.scalars(select(Course))}
    version = planner.latest_version(db)
    if version is not None:
        rows = db.execute(
            select(PlanBlock, Task).join(Task, PlanBlock.task_id == Task.id)
            .where(PlanBlock.plan_version_id == version.id)
        )
        for block, task in rows:
            events.append(OutEvent(
                uid=f"block-{task.id}-{block.start_at:%Y%m%dT%H%M}@kalibro",
                start=block.start_at, end=block.end_at,
                summary=f"{courses.get(task.course_id, '')}: {task.title}",
                description="Gepland door Kalibro",
            ))
    for deadline in db.scalars(select(Deadline).where(Deadline.ignored.is_(False))):
        start, end = deadline_event_bounds(deadline.due_at)
        label = "Examen" if deadline.kind == "exam" else "Deadline"
        events.append(OutEvent(
            uid=f"deadline-{deadline.id}@kalibro", start=start, end=end,
            summary=f"{label} {courses.get(deadline.course_id, '')}: {deadline.title}",
        ))
    return Response(
        content=write_calendar("Kalibro", events),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'inline; filename="kalibro.ics"'},
    )
