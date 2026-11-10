from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import TASK_STATUSES, TASK_TYPES


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
    estimate_s: int | None
    needs_manual_estimate: bool
    status: str


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
    uploaded_at: datetime


class SourceDetail(SourceOut):
    sections: list[SectionOut]
    tasks: list[TaskOut]
