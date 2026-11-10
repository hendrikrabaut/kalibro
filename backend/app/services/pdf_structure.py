"""Find the structure of a PDF without an LLM.

Order of attempts:
1. Bookmarks (the PDF's own table of contents, ``get_toc()``).
2. Headings recognised by font size relative to the body text.
3. Nothing found: one section for the whole document.

A PDF without a text layer is marked as scanned (no OCR in v1).
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf


EXERCISE_PATTERN = re.compile(
    r"^\s*(oefening|opgave|opdracht|vraag|exercise|question)\s*\d+",
    re.IGNORECASE | re.MULTILINE,
)
WORD_PATTERN = re.compile(r"\w+")

# A section with only exercises, e.g. "Exercises" at the end of each chapter.
EXERCISE_SECTION_PATTERN = re.compile(
    r"^\s*(\d+(\.\d+)*\.?\s+)?(exercises|oefeningen|opgaven|opdrachten|vragen|questions|problems)\b",
    re.IGNORECASE,
)
NUMBERED_ITEM_PATTERN = re.compile(r"^\s*(\d{1,3})[.)]\s", re.MULTILINE)

# A page with fewer characters than this counts as having no text layer.
MIN_TEXT_CHARS = 25
SCANNED_SHARE = 0.8

HEADING_SIZE_RATIO = 1.15
MAX_HEADING_LEVELS = 3
MAX_HEADING_LENGTH = 120


@dataclass
class ExtractedSection:
    title: str
    level: int
    page_start: int  # 1-based, inclusive, includes children
    page_end: int
    parent_index: int | None = None
    # Counts over the pages this section owns itself, excluding its children,
    # so summing over all sections never counts a page twice.
    own_pages: int = 0
    word_count: int = 0
    exercise_count: int = 0
    # Only for exercise sections: the number of questions "1. ... 2. ..." in it.
    numbered_items: int = 0


@dataclass
class ExtractedStructure:
    page_count: int
    scanned: bool
    method: str  # toc | fonts | none
    sections: list[ExtractedSection] = field(default_factory=list)


@dataclass
class _PageStats:
    words: int
    exercises: int
    chars: int


def extract_structure(path: Path | str) -> ExtractedStructure:
    with pymupdf.open(path) as document:
        texts = [page.get_text() for page in document]
        pages = [_page_stats(text) for text in texts]
        page_count = len(pages)

        if page_count == 0:
            return ExtractedStructure(page_count=0, scanned=False, method="none")

        empty_pages = sum(1 for page in pages if page.chars < MIN_TEXT_CHARS)
        scanned = empty_pages / page_count >= SCANNED_SHARE

        entries = _entries_from_toc(document)
        method = "toc"
        if not entries and not scanned:
            entries = _entries_from_fonts(document)
            method = "fonts"
        if not entries:
            title = Path(path).stem if not document.metadata.get("title") else document.metadata["title"]
            entries = [(1, title, 1)]
            method = "none"

    sections = _build_sections(entries, pages)
    for index, section in enumerate(sections):
        if EXERCISE_SECTION_PATTERN.match(section.title):
            following = sections[index + 1] if index + 1 < len(sections) else None
            section.numbered_items = count_numbered_items(_section_text(section, following, texts))

    return ExtractedStructure(page_count=page_count, scanned=scanned, method=method, sections=sections)


def _section_text(
    section: ExtractedSection, following: ExtractedSection | None, texts: list[str]
) -> str:
    """Text from the section's heading up to the next heading."""
    text = "\n".join(texts[section.page_start - 1 : section.page_end])
    start = text.find(section.title)
    if start > 0:
        text = text[start:]
    if following is not None and following.page_start <= section.page_end:
        end = text.find(following.title, len(section.title))
        if end > 0:
            text = text[:end]
    return text


def count_numbered_items(text: str) -> int:
    """Count questions numbered 1, 2, 3, ... in order. Stray numbers (footnotes,
    years) do not break the sequence, they are simply skipped."""
    expected = 1
    for match in NUMBERED_ITEM_PATTERN.finditer(text):
        if int(match.group(1)) == expected:
            expected += 1
    return expected - 1


def _page_stats(text: str) -> _PageStats:
    return _PageStats(
        words=len(WORD_PATTERN.findall(text)),
        exercises=len(EXERCISE_PATTERN.findall(text)),
        chars=len(text.strip()),
    )


def _entries_from_toc(document: pymupdf.Document) -> list[tuple[int, str, int]]:
    entries = []
    for level, title, page in document.get_toc(simple=True):
        title = " ".join(title.split())
        # Bookmarks pointing nowhere (page <= 0) are skipped.
        if title and page >= 1:
            entries.append((level, title, min(page, document.page_count)))
    return entries


def _entries_from_fonts(document: pymupdf.Document) -> list[tuple[int, str, int]]:
    lines: list[tuple[int, float, str]] = []  # (page, size, text)
    size_weight: Counter[float] = Counter()

    for page_number, page in enumerate(document, start=1):
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                spans = [span for span in line["spans"] if span["text"].strip()]
                if not spans:
                    continue
                text = " ".join("".join(span["text"] for span in spans).split())
                size = round(max(span["size"] for span in spans), 1)
                lines.append((page_number, size, text))
                size_weight[size] += len(text)

    if not size_weight:
        return []

    body_size = size_weight.most_common(1)[0][0]
    candidates = [
        (page, size, text)
        for page, size, text in lines
        if size >= body_size * HEADING_SIZE_RATIO
        and 2 <= len(text) <= MAX_HEADING_LENGTH
        and not text.replace(".", "").isdigit()  # page numbers, chapter digits alone
    ]

    # Merge titles that wrap over several lines.
    merged: list[tuple[int, float, str]] = []
    for page, size, text in candidates:
        if merged and merged[-1][0] == page and merged[-1][1] == size:
            merged[-1] = (page, size, f"{merged[-1][2]} {text}")
        else:
            merged.append((page, size, text))

    sizes = sorted({size for _, size, _ in merged}, reverse=True)[:MAX_HEADING_LEVELS]

    # A running header in a large font on every page is not a heading.
    repeated = {text for text, count in Counter(t for _, _, t in merged).items() if count > 2}

    return [
        (sizes.index(size) + 1, text, page)
        for page, size, text in merged
        if size in sizes and text not in repeated
    ]


def _build_sections(
    entries: list[tuple[int, str, int]], pages: list[_PageStats]
) -> list[ExtractedSection]:
    page_count = len(pages)
    sections: list[ExtractedSection] = []
    open_parents: list[int] = []  # indices of the current chain of ancestors

    for level, title, page in entries:
        while open_parents and sections[open_parents[-1]].level >= level:
            open_parents.pop()
        parent = open_parents[-1] if open_parents else None
        # Bookmarks may skip levels (1 -> 3); store the depth actually reached.
        level = sections[parent].level + 1 if parent is not None else 1
        sections.append(
            ExtractedSection(
                title=title, level=level, page_start=page, page_end=page, parent_index=parent
            )
        )
        open_parents.append(len(sections) - 1)

    # Full range: up to the page before the next section at the same or a higher level.
    for index, section in enumerate(sections):
        end = page_count
        for later in sections[index + 1 :]:
            if later.level <= section.level:
                end = max(section.page_start, later.page_start - 1)
                break
        section.page_end = end

    # Each page belongs to the last section starting on or before it.
    owner = 0
    for page_number in range(1, page_count + 1):
        while owner + 1 < len(sections) and sections[owner + 1].page_start <= page_number:
            owner += 1
        if sections[owner].page_start > page_number:
            continue  # front matter before the first section
        sections[owner].own_pages += 1
        sections[owner].word_count += pages[page_number - 1].words
        sections[owner].exercise_count += pages[page_number - 1].exercises

    return sections
