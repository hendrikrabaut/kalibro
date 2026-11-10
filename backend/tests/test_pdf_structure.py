"""PDFs are generated here on the fly: no course material in the repo."""

import pymupdf
import pytest

from app.services.pdf_structure import _PageStats, _build_sections, extract_structure


def _make_pdf(path, pages):
    """pages: list of lists of (text, fontsize) lines."""
    document = pymupdf.open()
    for lines in pages:
        page = document.new_page()
        y = 72
        for text, size in lines:
            page.insert_text((72, y), text, fontsize=size)
            y += size * 1.6
    return document


BODY = "Dit is gewone tekst over het onderwerp van deze cursus. " * 2


def test_bookmarks_give_tree_ranges_and_counts(tmp_path):
    path = tmp_path / "toc.pdf"
    document = _make_pdf(
        path,
        [
            [("Voorwoord", 11), (BODY, 11)],               # page 1: front matter
            [("Hoofdstuk 1", 18), (BODY, 11)],              # 2
            [("1.1 Begrippen", 14), (BODY, 11), ("Oefening 1", 11), ("Oefening 2", 11)],  # 3
            [(BODY, 11)],                                   # 4
            [("Hoofdstuk 2", 18), (BODY, 11), ("Opgave 3", 11)],  # 5
        ],
    )
    document.set_toc([[1, "Hoofdstuk 1", 2], [2, "1.1 Begrippen", 3], [1, "Hoofdstuk 2", 5]])
    document.save(path)

    result = extract_structure(path)

    assert result.method == "toc"
    assert result.page_count == 5
    assert not result.scanned
    chapter1, concepts, chapter2 = result.sections
    assert (chapter1.page_start, chapter1.page_end, chapter1.parent_index) == (2, 4, None)
    assert (concepts.page_start, concepts.page_end, concepts.parent_index) == (3, 4, 0)
    assert (chapter2.page_start, chapter2.page_end) == (5, 5)
    assert concepts.exercise_count == 2
    assert chapter2.exercise_count == 1
    # Chapter 1 owns only page 2; its child owns pages 3 and 4.
    assert concepts.word_count > chapter1.word_count > 0
    assert (chapter1.own_pages, concepts.own_pages, chapter2.own_pages) == (1, 2, 1)


def test_skipped_bookmark_levels_are_normalised():
    # Bookmarks in real PDFs sometimes jump from level 1 to 3.
    sections = _build_sections(
        [(1, "A", 1), (3, "A.1.1", 2)], [_PageStats(10, 0, 100), _PageStats(10, 0, 100)]
    )
    assert sections[1].level == 2
    assert sections[1].parent_index == 0


def test_headings_from_font_size_without_bookmarks(tmp_path):
    path = tmp_path / "fonts.pdf"
    document = _make_pdf(
        path,
        [
            [("Inleiding", 20), (BODY, 11), (BODY, 11)],
            [("Methode", 20), (BODY, 11), ("Deelvraag", 15), (BODY, 11)],
            [(BODY, 11), (BODY, 11)],
        ],
    )
    document.save(path)

    result = extract_structure(path)

    assert result.method == "fonts"
    assert [(s.level, s.title) for s in result.sections] == [
        (1, "Inleiding"),
        (1, "Methode"),
        (2, "Deelvraag"),
    ]
    assert result.sections[1].page_end == 3


def test_repeated_running_header_is_not_a_heading(tmp_path):
    path = tmp_path / "header.pdf"
    document = _make_pdf(
        path,
        [[("Cursus X", 16), ("Deel een", 22), (BODY, 11)]]
        + [[("Cursus X", 16), (BODY, 11)] for _ in range(3)],
    )
    document.save(path)

    titles = [s.title for s in extract_structure(path).sections]
    assert titles == ["Deel een"]


def test_pdf_without_text_is_marked_scanned(tmp_path):
    path = tmp_path / "scan.pdf"
    document = pymupdf.open()
    for _ in range(3):
        page = document.new_page()
        page.draw_rect(pymupdf.Rect(50, 50, 300, 300), fill=(0.5, 0.5, 0.5))
    document.save(path)

    result = extract_structure(path)

    assert result.scanned
    assert result.method == "none"
    assert len(result.sections) == 1
    assert (result.sections[0].page_start, result.sections[0].page_end) == (1, 3)
