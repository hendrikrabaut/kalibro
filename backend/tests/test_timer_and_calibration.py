import math
from datetime import datetime, timedelta

import pytest

from app.database import SessionLocal
from app.models import Course, StudySession, Task
from app.services.calibration import PRIOR_SIGMA, Calibrator, weekly_accuracy


@pytest.fixture
def task_ids(client):
    course = client.post("/api/courses", json={"name": "Netwerken"}).json()
    with SessionLocal() as db:
        tasks = [Task(course_id=course["id"], title=f"T{n}", task_type="reading", amount=10) for n in range(2)]
        db.add_all(tasks)
        db.commit()
        return [task.id for task in tasks]


def test_timer_freezes_estimate_and_switches_task(client, task_ids):
    first, second = task_ids
    state = client.post(f"/api/tasks/{first}/start").json()
    assert state["running"] and state["task"]["id"] == first
    assert state["task"]["estimate_at_start_s"] == 10 * 300
    assert state["task"]["status"] == "in_progress"

    state = client.post(f"/api/tasks/{second}/start").json()
    assert state["task"]["id"] == second
    sessions = client.get(f"/api/tasks/{first}/sessions").json()
    assert len(sessions) == 1 and sessions[0]["end_at"] is not None

    assert client.post("/api/timer/stop").json() == {"running": False, "session": None, "task": None, "elapsed_s": 0}


def test_complete_stops_timer_and_done_task_cannot_start(client, task_ids):
    client.post(f"/api/tasks/{task_ids[0]}/start")
    done = client.post(f"/api/tasks/{task_ids[0]}/complete").json()
    assert done["status"] == "done" and done["remaining_s"] == 0
    assert client.get("/api/timer").json()["running"] is False
    assert client.post(f"/api/tasks/{task_ids[0]}/start").status_code == 409


def test_manual_session_validation(client, task_ids):
    url = f"/api/tasks/{task_ids[0]}/sessions"
    ok = client.post(url, json={"start_at": "2026-11-09T09:00:00+01:00", "end_at": "2026-11-09T10:30:00+01:00"})
    assert ok.status_code == 201 and ok.json()["start_at"] == "2026-11-09T08:00:00+00:00"
    assert client.post(url, json={"start_at": "2026-11-09T10:00:00Z", "end_at": "2026-11-09T09:00:00Z"}).status_code == 422


def _finish(db, course_id, task_type, base_minutes, actual_minutes, completed=datetime(2026, 11, 3, 12), frozen=None):
    task = Task(course_id=course_id, title="t", task_type=task_type, amount=1,
                manual_estimate_s=base_minutes * 60, status="done", completed_at=completed,
                estimate_at_start_s=frozen if frozen is not None else base_minutes * 60)
    db.add(task)
    db.flush()
    db.add(StudySession(task_id=task.id, start_at=completed - timedelta(minutes=actual_minutes), end_at=completed))
    return task


def test_no_data_means_factor_one_and_prior_margin():
    with SessionLocal() as db:
        calibrator = Calibrator(db)
        factor = calibrator.factor(1, "reading")
    assert factor.factor == 1.0
    assert factor.sigma == pytest.approx(PRIOR_SIGMA)
    low, high = factor.margin(3600)
    assert low < 3600 < high


def test_shrinkage_pulls_few_observations_to_the_mean():
    with SessionLocal() as db:
        a, b = Course(name="A"), Course(name="B")
        db.add_all([a, b])
        db.flush()
        _finish(db, a.id, "reading", 60, 120)  # one task, twice as slow
        db.commit()
        calibrator = Calibrator(db)
        one = calibrator.factor(a.id, "reading").factor
        assert 1.0 < one < 2.0

        for _ in range(20):
            _finish(db, a.id, "reading", 60, 120)
        db.commit()
        many = Calibrator(db).factor(a.id, "reading").factor
        other_course = Calibrator(db).factor(b.id, "reading").factor
    assert one < many < 2.0 and many > 1.8
    # Another course borrows from the type average, but less strongly.
    assert 1.0 < other_course < many


def test_weekly_mape_uses_frozen_estimate():
    with SessionLocal() as db:
        course = Course(name="C")
        db.add(course)
        db.flush()
        # Estimated 60, took 120: APE 50%. Estimated 100, took 80: APE 25%.
        _finish(db, course.id, "reading", 60, 120, frozen=3600)
        _finish(db, course.id, "reading", 100, 80, frozen=6000)
        db.commit()
        weeks = weekly_accuracy(db)
    assert weeks[0]["week_start"].isoformat() == "2026-11-02"
    assert weeks[0]["mape"] == pytest.approx(37.5)
    assert weeks[0]["task_count"] == 2
