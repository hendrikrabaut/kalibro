from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AvailabilityException, AvailabilitySlot
from app.schemas import ExceptionIn, ExceptionOut, SlotIn, SlotOut


router = APIRouter(prefix="/api/availability", tags=["beschikbaarheid"])


def _check_range(start: str | None, end: str | None):
    if start is not None and end is not None and start >= end:
        raise HTTPException(422, "Het einde moet na het begin liggen")


@router.get("/slots", response_model=list[SlotOut])
def list_slots(db: Session = Depends(get_db)):
    return db.scalars(select(AvailabilitySlot).order_by(AvailabilitySlot.weekday, AvailabilitySlot.start_time)).all()


@router.post("/slots", response_model=SlotOut, status_code=201)
def create_slot(payload: SlotIn, db: Session = Depends(get_db)):
    _check_range(payload.start_time, payload.end_time)
    slot = AvailabilitySlot(**payload.model_dump())
    db.add(slot)
    db.commit()
    return slot


@router.delete("/slots/{slot_id}", status_code=204)
def delete_slot(slot_id: int, db: Session = Depends(get_db)):
    slot = db.get(AvailabilitySlot, slot_id)
    if slot is None:
        raise HTTPException(404, "Blok niet gevonden")
    db.delete(slot)
    db.commit()


@router.get("/exceptions", response_model=list[ExceptionOut])
def list_exceptions(db: Session = Depends(get_db)):
    return db.scalars(select(AvailabilityException).order_by(AvailabilityException.day)).all()


@router.post("/exceptions", response_model=ExceptionOut, status_code=201)
def create_exception(payload: ExceptionIn, db: Session = Depends(get_db)):
    if payload.available and (payload.start_time is None or payload.end_time is None):
        raise HTTPException(422, "Een extra blok heeft een begin- en eindtijd nodig")
    if (payload.start_time is None) != (payload.end_time is None):
        raise HTTPException(422, "Geef zowel begin als einde, of geen van beide")
    _check_range(payload.start_time, payload.end_time)
    exception = AvailabilityException(**payload.model_dump())
    db.add(exception)
    db.commit()
    return exception


@router.delete("/exceptions/{exception_id}", status_code=204)
def delete_exception(exception_id: int, db: Session = Depends(get_db)):
    exception = db.get(AvailabilityException, exception_id)
    if exception is None:
        raise HTTPException(404, "Uitzondering niet gevonden")
    db.delete(exception)
    db.commit()
