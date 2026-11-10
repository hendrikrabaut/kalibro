from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError

from app import models  # noqa: F401  (registers all tables)
from app.routes.courses import router as courses_router
from app.routes.sources import router as sources_router
from app.routes.tasks import router as tasks_router


FRONTEND_PATH = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(
    title="Kalibro API",
    description="Studieplanner die zijn schattingen kalibreert met je gelogde tijden",
    version="0.1.0",
)


@app.exception_handler(IntegrityError)
def handle_integrity_error(_request: Request, _error: IntegrityError):
    return JSONResponse(
        status_code=409,
        content={"detail": "Dit botst met bestaande data: een verwijzing bestaat niet, is nog in gebruik of moet uniek zijn"},
    )


app.include_router(courses_router)
app.include_router(sources_router)
app.include_router(tasks_router)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


# Mounted last, because "/" would otherwise catch the API routes.
if FRONTEND_PATH.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_PATH, html=True), name="frontend")
