from datetime import date, datetime

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

from app.timeutil import as_utc

from app.models import TASK_STATUSES, TASK_TYPES


# Stored as naive UTC; sent with an explicit offset so clients never guess.
UtcDatetime = Annotated[datetime, PlainSerializer(lambda moment: as_utc(moment).isoformat())]


class CourseIn(BaseModel):
    name: str = Field(min_length=1)
    color: str | None = None
    credits: float | None = Field(default=None, ge=0)
    ical_url: str | None = None


class CourseOut(CourseIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class SectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    parent_id: int | None
    title: str
    level: int
    position: int
    page_start: int
    page_end: int
    word_count: int
    exercise_count: int


class TaskOut(BaseModel):
    id: int
    course_id: int
    section_id: int | None
    deadline_id: int | None
    title: str
    task_type: str
    amount: float
    unit: str
    manual_estimate_s: int | None
    estimate_at_start_s: int | None
    base_estimate_s: int | None
    factor: float
    estimate_s: int | None
    estimate_low_s: int | None
    estimate_high_s: int | None
    logged_s: int
    remaining_s: int | None
    needs_manual_estimate: bool
    status: str


class TaskCreate(BaseModel):
    title: str = Field(min_length=1)
    task_type: str = Field(default="other", pattern=f"^({'|'.join(TASK_TYPES)})$")
    amount: float = Field(default=1, ge=0)
    manual_estimate_s: int | None = Field(default=None, ge=0)
    deadline_id: int | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    task_type: str | None = Field(default=None, pattern=f"^({'|'.join(TASK_TYPES)})$")
    amount: float | None = Field(default=None, ge=0)
    manual_estimate_s: int | None = Field(default=None, ge=0)
    deadline_id: int | None = None
    status: str | None = Field(default=None, pattern=f"^({'|'.join(TASK_STATUSES)})$")


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    course_id: int
    filename: str
    kind: str
    page_count: int
    scanned: bool
    structure_method: str
    uploaded_at: UtcDatetime


class SourceDetail(SourceOut):
    sections: list[SectionOut]
    tasks: list[TaskOut]


TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"


class DeadlineIn(BaseModel):
    title: str = Field(min_length=1)
    due_at: datetime  # with a timezone, or UTC when naive
    kind: str = Field(default="assignment", pattern="^(assignment|exam)$")


class DeadlineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    course_id: int
    title: str
    due_at: UtcDatetime
    kind: str
    origin: str


class SlotIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_time: str = Field(pattern=TIME_PATTERN)
    end_time: str = Field(pattern=TIME_PATTERN)


class SlotOut(SlotIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ExceptionIn(BaseModel):
    day: date
    available: bool = False
    start_time: str | None = Field(default=None, pattern=TIME_PATTERN)
    end_time: str | None = Field(default=None, pattern=TIME_PATTERN)
    note: str | None = None


class ExceptionOut(ExceptionIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class RateIn(BaseModel):
    unit: str = Field(min_length=1)
    seconds_per_unit: float = Field(gt=0)


class RateOut(RateIn):
    model_config = ConfigDict(from_attributes=True)
    task_type: str


class SessionIn(BaseModel):
    """A session added by hand, e.g. when you forgot the timer."""
    start_at: datetime
    end_at: datetime


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_id: int
    start_at: UtcDatetime
    end_at: UtcDatetime | None


class TimerOut(BaseModel):
    running: bool
    session: SessionOut | None = None
    task: TaskOut | None = None
    elapsed_s: int = 0


class PlanRequest(BaseModel):
    reason: str | None = None
