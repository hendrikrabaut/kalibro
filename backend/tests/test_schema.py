from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import pytest

from app.database import SessionLocal
from app.models import Course, Deadline, Section, Source, Task, TaskRate


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_default_rates_are_seeded():
    with SessionLocal() as db:
        rates = {rate.task_type: rate for rate in db.scalars(select(TaskRate))}
    assert {"reading", "slides", "exercises", "lab"} <= rates.keys()
    assert rates["slides"].unit == "slide"


def test_deleting_a_course_cascades_and_keeps_integrity():
    with SessionLocal() as db:
        course = Course(name="Databanken")
        db.add(course)
        db.flush()
        source = Source(
            course_id=course.id, filename="x.pdf", kind="pdf", sha256="abc",
            page_count=3, uploaded_at=datetime(2026, 11, 10),
        )
        db.add(source)
        db.flush()
        section = Section(source_id=source.id, title="H1", level=1, position=0, page_start=1, page_end=3)
        db.add(section)
        db.flush()
        db.add(Task(course_id=course.id, section_id=section.id, title="H1 lezen", task_type="reading", amount=3))
        db.commit()

        db.delete(course)
        db.commit()
        assert db.scalars(select(Task)).all() == []
        assert db.scalars(select(Section)).all() == []


def test_ical_uid_is_unique_per_course():
    with SessionLocal() as db:
        course = Course(name="Netwerken")
        db.add(course)
        db.flush()
        for _ in range(2):
            db.add(Deadline(course_id=course.id, title="Labo 1", due_at=datetime(2026, 12, 1), origin="ical", ical_uid="u1"))
        with pytest.raises(IntegrityError):
            db.commit()
