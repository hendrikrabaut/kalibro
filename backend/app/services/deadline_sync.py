from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, Deadline
from app.services.ical import FeedEvent, fetch_feed, parse_events


def apply_events(db: Session, course: Course, events: list[FeedEvent]) -> dict:
    existing = {
        d.ical_uid: d for d in db.scalars(
            select(Deadline).where(Deadline.course_id == course.id, Deadline.ical_uid.is_not(None))
        )
    }
    added = updated = 0
    for event in events:
        deadline = existing.get(event.uid)
        if deadline is None:
            db.add(Deadline(
                course_id=course.id, title=event.summary, due_at=event.due_at,
                kind=event.kind, origin="ical", ical_uid=event.uid,
            ))
            added += 1
        elif not deadline.ignored and (deadline.title, deadline.due_at) != (event.summary, event.due_at):
            # The platform is the source of truth for its own events.
            deadline.title, deadline.due_at = event.summary, event.due_at
            updated += 1
    db.commit()
    return {"added": added, "updated": updated, "events": len(events)}


def sync_course(db: Session, course: Course) -> dict:
    if not course.ical_url:
        raise ValueError("Dit vak heeft geen iCal-feed")
    return apply_events(db, course, parse_events(fetch_feed(course.ical_url)))
