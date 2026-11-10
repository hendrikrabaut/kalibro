from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import TaskRate
from app.schemas import RateIn, RateOut


router = APIRouter(prefix="/api/rates", tags=["tempo"])


@router.get("", response_model=list[RateOut])
def list_rates(db: Session = Depends(get_db)):
    return db.scalars(select(TaskRate).order_by(TaskRate.task_type)).all()


@router.put("/{task_type}", response_model=RateOut)
def update_rate(task_type: str, payload: RateIn, db: Session = Depends(get_db)):
    rate = db.get(TaskRate, task_type)
    if rate is None:
        raise HTTPException(404, "Onbekend taaktype")
    rate.unit = payload.unit
    rate.seconds_per_unit = payload.seconds_per_unit
    db.commit()
    return rate
