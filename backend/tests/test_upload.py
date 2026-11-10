import io

import pymupdf
import pytest

from app import database


BODY = "Dit is gewone tekst over het onderwerp van deze cursus. " * 2


def _pdf_bytes(pages, toc=None, scanned=False):
    document = pymupdf.open()
    for lines in pages:
        page = document.new_page()
        if scanned:
            page.draw_rect(pymupdf.Rect(50, 50, 300, 300), fill=(0.5, 0.5, 0.5))
            continue
        y = 72
        for text in lines:
            page.insert_text((72, y), text, fontsize=11)
            y += 18
    if toc:
        document.set_toc(toc)
    return document.tobytes()


@pytest.fixture
def course_id(client):
    return client.post("/api/courses", json={"name": "Databanken"}).json()["id"]


def _upload(client, course_id, data, name="cursus.pdf"):
    return client.post(
        f"/api/courses/{course_id}/sources",
        files={"file": (name, io.BytesIO(data), "application/pdf")},
    )


def test_upload_creates_sections_and_estimated_tasks(client, course_id):
    data = _pdf_bytes(
        [[BODY], [BODY], [BODY, "Oefening 1", "Oefening 2"], [BODY]],
        toc=[[1, "H1", 1], [2, "H1.1", 2], [1, "H2", 4]],
    )
    response = _upload(client, course_id, data)
    assert response.status_code == 201
    body = response.json()

    assert body["structure_method"] == "toc"
    assert [s["title"] for s in body["sections"]] == ["H1", "H1.1", "H2"]
    assert body["sections"][1]["parent_id"] == body["sections"][0]["id"]

    tasks = {(t["title"], t["task_type"]): t for t in body["tasks"]}
    assert tasks[("H1.1", "reading")]["amount"] == 2
    assert tasks[("H1.1", "reading")]["estimate_s"] == 2 * 300
    assert tasks[("H1.1: oefeningen", "exercises")]["estimate_s"] == 2 * 900
    assert tasks[("H1.1: oefeningen", "exercises")]["unit"] == "exercise"

    stored = list(database.UPLOAD_DIR.glob("*.pdf"))
    assert len(stored) == 1
    assert not list(database.UPLOAD_DIR.glob("*.part"))

    assert len(client.get(f"/api/courses/{course_id}/tasks").json()) == 4


def test_same_file_twice_is_refused(client, course_id):
    data = _pdf_bytes([[BODY]])
    assert _upload(client, course_id, data).status_code == 201
    response = _upload(client, course_id, data, name="kopie.pdf")
    assert response.status_code == 409
    assert "cursus.pdf" in response.json()["detail"]


def test_non_pdf_is_refused(client, course_id):
    response = _upload(client, course_id, b"geen pdf", name="nep.pdf")
    assert response.status_code == 400
    assert not list(database.UPLOAD_DIR.glob("*.part"))


def test_unknown_course_is_404(client):
    assert _upload(client, 999, _pdf_bytes([[BODY]])).status_code == 404


def test_scanned_pdf_asks_for_manual_estimate(client, course_id):
    body = _upload(client, course_id, _pdf_bytes([[], [], []], scanned=True)).json()
    assert body["scanned"]
    (task,) = body["tasks"]
    assert task["needs_manual_estimate"]
    assert task["estimate_s"] is None

    updated = client.patch(f"/api/tasks/{task['id']}", json={"manual_estimate_s": 5400}).json()
    assert not updated["needs_manual_estimate"]
    assert updated["estimate_s"] == 5400


def test_patch_rejects_unknown_task_type(client, course_id):
    task = _upload(client, course_id, _pdf_bytes([[BODY]])).json()["tasks"][0]
    assert client.patch(f"/api/tasks/{task['id']}", json={"task_type": "slapen"}).status_code == 422


def test_deleting_source_removes_file_and_tasks(client, course_id):
    source = _upload(client, course_id, _pdf_bytes([[BODY]])).json()
    assert client.delete(f"/api/sources/{source['id']}").status_code == 204
    assert client.get(f"/api/courses/{course_id}/tasks").json() == []
    assert not list(database.UPLOAD_DIR.glob("*.pdf"))
