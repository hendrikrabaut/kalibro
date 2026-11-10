from datetime import datetime

from app.database import SessionLocal
from app.models import Course
from app.services.deadline_sync import apply_events
from app.services.ical import OutEvent, parse_events, write_calendar


FEED = (
    "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
    "BEGIN:VEVENT\r\nUID:a1\r\nSUMMARY:Indienen labo\\, deel 1\r\n"
    "DTSTART;TZID=Europe/Brussels:20261201T235900\r\nEND:VEVENT\r\n"
    "BEGIN:VEVENT\r\nUID:a2\r\nSUMMARY:Examen databanken\r\nDTSTART:20270115T080000Z\r\nEND:VEVENT\r\n"
    "BEGIN:VEVENT\r\nUID:a3\r\nSUMMARY:Project met een heel lange titel die over meerdere\r\n"
    "  regels gevouwen wordt\r\nDTSTART;VALUE=DATE:20261210\r\nEND:VEVENT\r\n"
    "END:VCALENDAR\r\n"
)


def test_parse_events():
    events = {event.uid: event for event in parse_events(FEED)}
    assert events["a1"].summary == "Indienen labo, deel 1"
    assert events["a1"].due_at == datetime(2026, 12, 1, 22, 59)
    assert events["a2"].kind == "exam"
    assert events["a2"].due_at == datetime(2027, 1, 15, 8)
    assert events["a3"].summary.endswith("meerdere regels gevouwen wordt")
    assert events["a3"].due_at == datetime(2026, 12, 10, 22, 59)  # end of day, local


def test_sync_is_idempotent_and_respects_ignored(client):
    course_id = client.post("/api/courses", json={"name": "Databanken"}).json()["id"]
    with SessionLocal() as db:
        course = db.get(Course, course_id)
        assert apply_events(db, course, parse_events(FEED))["added"] == 3
        assert apply_events(db, course, parse_events(FEED)) == {"added": 0, "updated": 0, "events": 3}

    exam = next(d for d in client.get(f"/api/courses/{course_id}/deadlines").json() if d["kind"] == "exam")
    assert client.delete(f"/api/deadlines/{exam['id']}").status_code == 204
    with SessionLocal() as db:
        apply_events(db, db.get(Course, course_id), parse_events(FEED))
    assert len(client.get(f"/api/courses/{course_id}/deadlines").json()) == 2


def test_sync_without_feed_is_400(client):
    course_id = client.post("/api/courses", json={"name": "X"}).json()["id"]
    assert client.post(f"/api/courses/{course_id}/deadlines/sync").status_code == 400


def test_written_calendar_round_trips():
    text = write_calendar("Kalibro", [OutEvent("u1", datetime(2026, 11, 16, 9), datetime(2026, 11, 16, 10), "Vak: lezen; deel 2, " + "x" * 80)])
    assert all(len(line.encode()) <= 75 for line in text.split("\r\n"))
    (event,) = parse_events(text)
    assert event.summary == "Vak: lezen; deel 2, " + "x" * 80
