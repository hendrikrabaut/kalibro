"""Turn the section tree into tasks at a sensible size.

A task is a study unit, usually a chapter. Walking down the tree, the first
section of at most MAX_UNIT_PAGES becomes one task, its children included: parts
are split into chapters, chapters are not split into their subheadings. When a
section is too big, its children are used instead, and small neighbouring
children are grouped up to about GROUP_TARGET_PAGES.

Front and back matter (cover, index, solutions, ...) gets no task. An exercise
section becomes an exercises task, and its pages leave the reading task.
"""

import re
from dataclasses import dataclass

from app.services.pdf_structure import EXERCISE_SECTION_PATTERN, ExtractedSection


MAX_UNIT_PAGES = 60
GROUP_TARGET_PAGES = 25

# A section with only a few pages of its own before its children (a part's
# title page) is not worth a task.
MIN_INTRO_PAGES = 3

SKIP_PATTERN = re.compile(
    r"^\s*("
    r"cover|title page|titelpagina|copyright|colofon|colophon|"
    r"(brief |table of )?contents|inhoud(stafel|sopgave)?|"
    r"preface|foreword|voorwoord|woord vooraf|acknowledge?ments?|dankwoord|"
    r"about the authors?|over de auteurs?|"
    r"index|register|trefwoorden(register|lijst)?|"
    r"bibliogra(phy|fie)|references|referenties|literatuur(lijst)?|bronnen(lijst)?|"
    r".*\bsolutions?\b.*|.*\boplossingen\b.*"
    r")\s*$",
    re.IGNORECASE,
)


@dataclass
class TaskSpec:
    section_index: int
    title: str
    task_type: str  # reading | exercises
    amount: float


def is_skipped(section: ExtractedSection) -> bool:
    return bool(SKIP_PATTERN.match(section.title))


def is_exercise_section(section: ExtractedSection) -> bool:
    return bool(EXERCISE_SECTION_PATTERN.match(section.title))


def build_tasks(sections: list[ExtractedSection]) -> list[TaskSpec]:
    children: dict[int | None, list[int]] = {}
    for index, section in enumerate(sections):
        children.setdefault(section.parent_index, []).append(index)

    def size(index: int) -> int:
        return sections[index].page_end - sections[index].page_start + 1

    def tasks_for(indices: list[int], anchor: int, title: str) -> list[TaskSpec]:
        """One reading and one exercises task covering these whole subtrees."""
        reading_pages = 0
        questions = 0
        stack = list(indices)
        while stack:
            index = stack.pop()
            section = sections[index]
            if is_skipped(section):
                continue
            if is_exercise_section(section):
                questions += max(section.numbered_items, 1)
                continue  # its pages and subsections are exercises, not reading
            reading_pages += section.own_pages
            questions += section.exercise_count
            stack.extend(children.get(index, []))

        tasks = []
        if reading_pages:
            tasks.append(TaskSpec(anchor, title, "reading", reading_pages))
        if questions:
            tasks.append(TaskSpec(anchor, f"{title}: oefeningen", "exercises", questions))
        return tasks

    def visit(index: int) -> list[TaskSpec]:
        section = sections[index]
        kids = [kid for kid in children.get(index, []) if not is_skipped(sections[kid])]
        if is_skipped(section):
            return []
        if not kids or size(index) <= MAX_UNIT_PAGES:
            return tasks_for([index], index, section.title)

        tasks: list[TaskSpec] = []
        if section.own_pages >= MIN_INTRO_PAGES:
            tasks.append(TaskSpec(index, f"{section.title}: inleiding", "reading", section.own_pages))

        group: list[int] = []

        def flush():
            if group:
                first, last = sections[group[0]].title, sections[group[-1]].title
                span = first if len(group) == 1 else f"{first} – {last}"
                tasks.extend(tasks_for(group, group[0], f"{section.title}: {span}"))
                group.clear()

        for kid in kids:
            if is_exercise_section(sections[kid]):
                flush()
                tasks.extend(tasks_for([kid], kid, section.title))
            elif size(kid) > GROUP_TARGET_PAGES // 2:
                flush()
                tasks.extend(visit(kid))  # a chapter in a part: its own task(s)
            else:
                if group and sum(size(i) for i in group) + size(kid) > GROUP_TARGET_PAGES:
                    flush()
                group.append(kid)
        flush()
        return tasks

    tasks: list[TaskSpec] = []
    for root in children.get(None, []):
        tasks.extend(visit(root))
    return tasks
