from app.services.pdf_structure import ExtractedSection, count_numbered_items
from app.services.task_builder import build_tasks


def _tree(rows):
    """rows: (level, title, page_start, page_end, own_pages[, numbered_items])."""
    sections, chain = [], []
    for level, title, start, end, own, *rest in rows:
        chain = chain[: level - 1]
        sections.append(ExtractedSection(
            title=title, level=level, page_start=start, page_end=end,
            parent_index=chain[-1] if chain else None, own_pages=own,
            numbered_items=rest[0] if rest else 0,
        ))
        chain.append(len(sections) - 1)
    return sections


def _summary(tasks):
    return [(t.task_type, t.amount, t.title) for t in tasks]


def test_parts_split_into_chapters_and_chapters_stay_whole():
    sections = _tree([
        (1, "Cover", 1, 1, 1),
        (1, "Table of Contents", 2, 5, 4),
        (1, "Part I", 6, 105, 2),
        (2, "Chapter 1", 8, 47, 10),
        (3, "1.1 Basics", 18, 37, 20),
        (3, "1.2 More", 38, 45, 8),
        (3, "Exercises", 46, 47, 2, 12),
        (2, "Chapter 2", 48, 105, 58),
        (1, "Index", 106, 110, 5),
    ])

    assert _summary(build_tasks(sections)) == [
        ("reading", 38, "Chapter 1"),
        ("exercises", 12, "Chapter 1: oefeningen"),
        ("reading", 58, "Chapter 2"),
    ]


def test_too_big_chapter_is_cut_into_groups_of_subsections():
    rows = [(1, "Chapter 7", 1, 100, 0)]
    rows += [(2, f"7.{n}", 1 + (n - 1) * 10, n * 10, 10) for n in range(1, 11)]
    titles = [t.title for t in build_tasks(_tree(rows))]

    # Subsections of 10 pages are grouped in pairs (target 25 pages).
    assert titles[0] == "Chapter 7: 7.1 – 7.2"
    assert len(titles) == 5


def test_part_title_page_gets_no_task_but_a_real_intro_does():
    sections = _tree([
        (1, "Part I", 1, 80, 1),
        (2, "Chapter 1", 2, 80, 79),
        (1, "Big Chapter", 81, 180, 5),
        (2, "Section A", 86, 180, 95),
    ])
    titles = [t.title for t in build_tasks(sections)]
    assert "Part I: inleiding" not in titles
    assert "Big Chapter: inleiding" in titles


def test_solutions_appendix_is_skipped():
    sections = _tree([
        (1, "Appendix A. Exercise Solutions", 1, 30, 1),
        (2, "Chapter 1: Landscape", 1, 30, 29),
        (1, "Oplossingen hoofdstuk 3", 31, 40, 10),
    ])
    assert build_tasks(sections) == []


def test_numbered_items_ignore_footnotes_and_years():
    text = "Exercises\n1. What is ML?\n11 Wolpert, 1996.\n2. Why?\n 3) And this?\n2020. year\n4. Last"
    assert count_numbered_items(text) == 4
