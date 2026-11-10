from datetime import date, datetime, timedelta

from app.database import SessionLocal
from app.models import AvailabilityException, AvailabilitySlot, Course, Deadline, Task
from app.services.planner import (
    MIN_BLOCK_S, WorkItem, free_intervals, gather, feasibility, make_plan, plan_overview, schedule,
)

# Monday 16 November 2026, 08:00 UTC = 09:00 in Brussels (winter time).
NOW = datetime(2026, 11, 16, 8, 0)


WEEKDAYS_10_12 = tuple((d, "10:00", "12:00") for d in range(5))


def _setup(db, tasks, slots=WEEKDAYS_10_12):
    for weekday, start, end in slots:
        db.add(AvailabilitySlot(weekday=weekday, start_time=start, end_time=end))
    course = Course(name="Vak")
    db.add(course)
    db.flush()
    created = []
    for title, minutes, due in tasks:
        deadline_id = None
        if due is not None:
            deadline = Deadline(course_id=course.id, title=f"DL {title}", due_at=due)
            db.add(deadline)
            db.flush()
            deadline_id = deadline.id
        task = Task(course_id=course.id, title=title, task_type="other", amount=1,
                    manual_estimate_s=minutes * 60, deadline_id=deadline_id)
        db.add(task)
        created.append(task)
    db.commit()
    return created


def test_free_time_is_local_and_respects_exceptions():
    with SessionLocal() as db:
        _setup(db, [])
        db.add(AvailabilityException(day=date(2026, 11, 17), available=False))  # Tuesday off
        db.add(AvailabilityException(day=date(2026, 11, 18), available=False, start_time="11:00", end_time="12:00"))
        db.add(AvailabilityException(day=date(2026, 11, 21), available=True, start_time="14:00", end_time="15:30"))
        db.commit()
        intervals = free_intervals(db, NOW, NOW + timedelta(days=6))

    assert intervals == [
        (datetime(2026, 11, 16, 9), datetime(2026, 11, 16, 11)),   # 10-12 local
        (datetime(2026, 11, 18, 9), datetime(2026, 11, 18, 10)),   # cut 11-12
        (datetime(2026, 11, 19, 9), datetime(2026, 11, 19, 11)),
        (datetime(2026, 11, 20, 9), datetime(2026, 11, 20, 11)),
        (datetime(2026, 11, 21, 13), datetime(2026, 11, 21, 14, 30)),  # Saturday extra
    ]


def test_summer_time_shifts_utc():
    with SessionLocal() as db:
        _setup(db, [])
        intervals = free_intervals(db, datetime(2027, 6, 7, 0), datetime(2027, 6, 8, 0))
    assert intervals == [(datetime(2027, 6, 7, 8), datetime(2027, 6, 7, 10))]


def test_earliest_deadline_first_and_splitting():
    day = timedelta(days=1)
    free = [(NOW, NOW + timedelta(hours=2)), (NOW + day, NOW + day + timedelta(hours=2))]
    items = [
        WorkItem(1, 90 * 60, NOW + 5 * day, (0,)),
        WorkItem(2, 60 * 60, NOW + 2 * day, (1,)),
        WorkItem(3, 30 * 60, None, (2,)),
    ]
    result = schedule(free, items)
    assert [(task, (end - start).seconds // 60) for task, start, end in result.blocks] == [
        (2, 60), (1, 60), (1, 30), (3, 30),
    ]
    assert result.unscheduled_s == {}


def test_no_leftover_piece_shorter_than_minimum():
    free = [(NOW, NOW + timedelta(minutes=50)), (NOW + timedelta(days=1), NOW + timedelta(days=1, hours=2))]
    result = schedule(free, [WorkItem(1, 60 * 60, None, (0,))])
    lengths = [(end - start).seconds for _, start, end in result.blocks]
    assert sum(lengths) == 3600
    assert min(lengths) >= MIN_BLOCK_S


def test_feasibility_ok_tight_and_infeasible():
    with SessionLocal() as db:
        # Mon-Fri 2 h a day. Friday 20 Nov 12:00 local = 11:00 UTC: 10 h available.
        friday = datetime(2026, 11, 20, 11)
        _setup(db, [("klein", 120, friday)])
        result = {row["title"]: row["status"] for row in feasibility(gather(db, NOW))}
        assert result == {"DL klein": "ok"}

    with SessionLocal() as db:
        db.query(Task).delete(); db.query(Deadline).delete(); db.query(AvailabilitySlot).delete(); db.query(Course).delete(); db.commit()
        _setup(db, [("krap", 9 * 60, datetime(2026, 11, 20, 11))])
        assert feasibility(gather(db, NOW))[0]["status"] == "tight"

    with SessionLocal() as db:
        db.query(Task).delete(); db.query(Deadline).delete(); db.query(AvailabilitySlot).delete(); db.query(Course).delete(); db.commit()
        _setup(db, [("teveel", 11 * 60, datetime(2026, 11, 20, 11))])
        overview = plan_overview(db, NOW)
        assert overview["deadlines"][0]["status"] == "infeasible"
        assert [t["title"] for t in overview["late_tasks"]] == ["teveel"]


def test_replanning_makes_a_new_version_and_uses_remaining_time():
    with SessionLocal() as db:
        (task,) = _setup(db, [("lezen", 120, None)])
        first = make_plan(db, now=NOW)
        task.status = "done"
        db.commit()
        second = make_plan(db, reason="achter", now=NOW + timedelta(days=1))
        assert second.id == first.id + 1
        overview = plan_overview(db, NOW + timedelta(days=1))
        assert overview["version"].reason == "achter"
        assert overview["blocks"] == []


def test_plan_endpoint_and_calendar(client):
    with SessionLocal() as db:
        _setup(db, [("hoofdstuk 1", 60, datetime(2030, 1, 1))])
    body = client.post("/api/plan", json={"reason": "eerste"}).json()
    assert body["version"]["reason"] == "eerste"
    assert body["blocks"] and body["blocks"][0]["start_at"].endswith("+00:00")

    ics = client.get("/api/calendar.ics")
    assert ics.headers["content-type"].startswith("text/calendar")
    assert "SUMMARY:Vak: hoofdstuk 1" in ics.text
    assert "SUMMARY:Deadline Vak: DL hoofdstuk 1" in ics.text


def _evenings(count, hours=2):
    return [(NOW + timedelta(days=d, hours=10), NOW + timedelta(days=d, hours=10 + hours)) for d in range(count)]


def _courses_per_block(result, course_of):
    per_block = []
    for task_id, start, _ in result.blocks:
        key = start.date()
        if not per_block or per_block[-1][0] != key:
            per_block.append((key, course_of[task_id]))
    return [course for _, course in per_block]


def test_courses_alternate_per_block():
    items = [WorkItem(n, 120 * 60, None, (n,), course_id=1) for n in range(1, 4)]
    items += [WorkItem(n, 120 * 60, None, (n,), course_id=2) for n in range(11, 14)]
    result = schedule(_evenings(6), items)
    course_of = {item.task_id: item.course_id for item in items}
    assert _courses_per_block(result, course_of) == [1, 2, 1, 2, 1, 2]


def test_alternating_never_costs_a_deadline():
    # Course 1 needs all of the first three evenings for its exam on day 3.
    exam = NOW + timedelta(days=2, hours=13)
    items = [WorkItem(n, 120 * 60, exam, (n,), course_id=1) for n in range(1, 4)]
    items += [WorkItem(n, 120 * 60, None, (n,), course_id=2) for n in range(11, 14)]
    result = schedule(_evenings(6), items)
    course_of = {item.task_id: item.course_id for item in items}
    assert _courses_per_block(result, course_of) == [1, 1, 1, 2, 2, 2]
    assert all(result.finish[n] <= exam for n in range(1, 4))


def test_alternating_with_slack_still_alternates_before_a_deadline():
    exam = NOW + timedelta(days=5, hours=13)
    items = [WorkItem(n, 120 * 60, exam, (n,), course_id=1) for n in range(1, 4)]
    items += [WorkItem(n, 120 * 60, None, (n,), course_id=2) for n in range(11, 13)]
    result = schedule(_evenings(6), items)
    course_of = {item.task_id: item.course_id for item in items}
    assert _courses_per_block(result, course_of)[:2] == [1, 2]
    assert all(result.finish[n] <= exam for n in range(1, 4))


def test_scheduling_is_fast_enough_for_the_pi():
    import time

    items = [
        WorkItem(course * 100 + n, 90 * 60, NOW + timedelta(weeks=4 + course), (n,), course_id=course)
        for course in range(5) for n in range(40)
    ]
    started = time.perf_counter()
    schedule(_evenings(180), items)
    # The Pi 3 is roughly 10x slower than a laptop.
    assert time.perf_counter() - started < 1.0
