import math

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Course
from app.services.calibration import Calibrator, PRIOR_WEIGHT, weekly_accuracy


router = APIRouter(prefix="/api/calibration", tags=["kalibratie"])


@router.get("")
def read_calibration(db: Session = Depends(get_db)):
    """Current correction factors per task type and per course."""
    calibrator = Calibrator(db)
    courses = list(db.scalars(select(Course).order_by(Course.name)))
    rows = []
    for task_type in calibrator.rates:
        for course in courses:
            factor = calibrator.factor(course.id, task_type)
            if factor.sample_size or calibrator.by_type.get(task_type):
                rows.append({
                    "course_id": course.id, "course": course.name, "task_type": task_type,
                    "factor": round(factor.factor, 3), "sample_size": factor.sample_size,
                })
    return {
        "finished_tasks": len(calibrator.observations),
        "global_factor": round(math.exp(calibrator.global_mean), 3),
        "type_factors": {t: round(math.exp(m), 3) for t, m in calibrator.type_means.items()},
        "sigma": round(calibrator.sigma, 3),
        "prior_weight": PRIOR_WEIGHT,
        "factors": rows,
    }


@router.get("/accuracy")
def read_accuracy(db: Session = Depends(get_db)):
    """Estimation error (MAPE, %) per week: the number that should go down."""
    return weekly_accuracy(db)
