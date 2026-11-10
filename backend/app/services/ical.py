"""Minimal iCalendar reading and writing: enough for deadline feeds and the plan.

Reading handles line folding, UTC times, TZID times and all-day dates.
"""

import re
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.config import LOCAL_TZ
from app.timeutil import utc_naive


EXAM_PATTERN = re.compile(r"\b(examen|exam|toets|test|tentamen)\b", re.IGNORECASE)
FETCH_TIMEOUT_S = 20
MAX_FEED_BYTES = 5 * 1024 * 1024


@dataclass
class FeedEvent:
    uid: str
    summary: str
    due_at: datetime  # naive UTC
    kind: str


def _unfold(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        elif raw:
            lines.append(raw)
    return lines


def _unescape(value: str) -> str:
    return (value.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",")
            .replace("\\;", ";").replace("\\\\", "\\"))


def _parse_moment(params: dict[str, str], value: str) -> datetime:
    value = value.strip()
    if params.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", value):
        # All-day: due at the end of that day, local time.
        day = date(int(value[:4]), int(value[4:6]), int(value[6:8]))
        return utc_naive(datetime.combine(day, time(23, 59), tzinfo=LOCAL_TZ))
    moment = datetime.strptime(value.rstrip("Z")[:15], "%Y%m%dT%H%M%S")
    if value.endswith("Z"):
        return moment
    try:
        zone = ZoneInfo(params["TZID"]) if "TZID" in params else LOCAL_TZ
    except ZoneInfoNotFoundError:
        zone = LOCAL_TZ
    return utc_naive(moment.replace(tzinfo=zone))


def parse_events(text: str) -> list[FeedEvent]:
    events: list[FeedEvent] = []
    current: dict[str, tuple[dict[str, str], str]] | None = None
    for line in _unfold(text):
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            if current is not None and "UID" in current and ("DTSTART" in current or "DUE" in current):
                params, value = current.get("DUE") or current["DTSTART"]
                summary = _unescape(current.get("SUMMARY", ({}, "Deadline"))[1]).strip() or "Deadline"
                try:
                    due_at = _parse_moment(params, value)
                except ValueError:
                    current = None
                    continue
                events.append(FeedEvent(
                    uid=current["UID"][1].strip(), summary=summary, due_at=due_at,
                    kind="exam" if EXAM_PATTERN.search(summary) else "assignment",
                ))
            current = None
            continue
        if current is None or ":" not in line:
            continue
        head, value = line.split(":", 1)
        name, *raw_params = head.split(";")
        params = dict(p.split("=", 1) for p in raw_params if "=" in p)
        current.setdefault(name.upper(), (params, value))
    return events


def fetch_feed(url: str) -> str:
    if not url.startswith(("https://", "http://", "webcal://")):
        raise ValueError("Een feed-URL begint met https://, http:// of webcal://")
    url = "https://" + url[len("webcal://"):] if url.startswith("webcal://") else url
    request = urllib.request.Request(url, headers={"User-Agent": "Kalibro/0.1"})
    with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_S) as response:
        data = response.read(MAX_FEED_BYTES + 1)
    if len(data) > MAX_FEED_BYTES:
        raise ValueError("De feed is groter dan 5 MB")
    return data.decode("utf-8", errors="replace")


# ---------------------------------------------------------------- writing

def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    encoded = line.encode()
    if len(encoded) <= 75:
        return line
    parts, current = [], b""
    for char in line:
        piece = char.encode()
        if len(current) + len(piece) > (75 if not parts else 74):
            parts.append(current.decode())
            current = b""
        current += piece
    parts.append(current.decode())
    return "\r\n ".join(parts)


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y%m%dT%H%M%SZ")


@dataclass
class OutEvent:
    uid: str
    start: datetime  # naive UTC
    end: datetime
    summary: str
    description: str = ""


def write_calendar(name: str, events: list[OutEvent]) -> str:
    now = _stamp(datetime.now(UTC).replace(tzinfo=None))
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Kalibro//Studieplanner//NL",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH", f"X-WR-CALNAME:{_escape(name)}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT1H", "X-PUBLISHED-TTL:PT1H",
    ]
    for event in events:
        lines += [
            "BEGIN:VEVENT", f"UID:{event.uid}", f"DTSTAMP:{now}",
            f"DTSTART:{_stamp(event.start)}", f"DTEND:{_stamp(event.end)}",
            f"SUMMARY:{_escape(event.summary)}",
        ]
        if event.description:
            lines.append(f"DESCRIPTION:{_escape(event.description)}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


def deadline_event_bounds(due_at: datetime) -> tuple[datetime, datetime]:
    """A deadline shows as a 15-minute event ending at the deadline."""
    return due_at - timedelta(minutes=15), due_at
