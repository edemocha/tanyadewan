"""Debate pages -> speaker turns.

The debate is flattened into one string with a style per character (bold, italic, page), so a
speaker label that wraps across a line or page break is still one bold run.

- label      a bold run at the start of a line ending in ":" (colon bold or just after)
- heading    a whole bold line, mostly upper case, no colon      -> section changes
- question   "N." line, then bold "Name [Constituency]" + " minta …"  -> written oral question
- stage      an italic "[…]" inside a turn ("[Tepuk]")            -> moved to stage_directions
- time mark  "■1040" lines                                         -> times on the turn they fall in
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from tanyadewan.parse.extract import Page, debate_start
from tanyadewan.parse.labels import LABEL_START, Label, parse_label

SECTION_KEYWORDS = [
    ("WAKTU PERTANYAAN-PERTANYAAN MENTERI", "minister_question_time"),
    ("PERTANYAAN-PERTANYAAN BAGI JAWAB LISAN", "oral_questions"),
    ("PERTANYAAN-PERTANYAAN BAGI JAWAB BERTULIS", "written_questions"),
    ("RANG UNDANG-UNDANG", "bill"),
    ("USUL", "motion"),
    ("TITAH", "royal_address"),
    ("PENERANGAN", "ministerial_statement"),
    ("KENYATAAN", "ministerial_statement"),
    ("PEMASYHURAN", "announcement"),
    ("UCAPAN", "speech"),
]
_QNUM = re.compile(r"^(\d{1,3})\.\s*$")
_STAGE = re.compile(r"\[[^\[\]]{1,150}\]")


@dataclass
class Turn:
    seq: int
    kind: str  # speech | written_question | action (label with only a stage direction, e.g. [Bangun])
    label: Label
    text: str
    section: str
    section_heading: str | None
    subheading: str | None
    question_no: int | None  # printed oral question number
    question_group: int | None = (
        None  # which question (oral or minister's question time) this turn belongs to
    )
    stage_directions: list[str] = field(default_factory=list)
    times: list[str] = field(default_factory=list)
    page_start: int = 0
    page_end: int = 0
    char_start: int = 0  # offset of the label in the flattened debate text (for remapping labels later)
    char_end: int = 0


@dataclass
class Stream:
    text: str
    bold: bytearray
    italic: bytearray
    page: list[int]
    line_start: list[int]  # offsets where each line starts
    times: list[tuple[int, str]]  # (offset, "1040")


def flatten(pages: list[Page]) -> Stream:
    parts: list[str] = []
    bold, italic = bytearray(), bytearray()
    page_of: list[int] = []
    line_start: list[int] = []
    times: list[tuple[int, str]] = []
    pos = 0
    prev_bold_end = False
    for page in pages:
        for line in page.lines:
            if line.time_mark:
                times.append((pos, line.time_mark))
                continue
            first_bold = line.spans[0].bold
            if pos:  # line break, bold if it joins two bold pieces (a wrapped label or heading)
                parts.append("\n")
                bold.append(1 if (prev_bold_end and first_bold) else 0)
                italic.append(0)
                page_of.append(page.number)
                pos += 1
            line_start.append(pos)
            for s in line.spans:
                parts.append(s.text)
                bold.extend([1 if s.bold else 0] * len(s.text))
                italic.extend([1 if s.italic else 0] * len(s.text))
                page_of.extend([page.number] * len(s.text))
                pos += len(s.text)
            prev_bold_end = line.spans[-1].bold or not line.spans[-1].text.strip()
    return Stream("".join(parts), bold, italic, page_of, line_start, times)


def bold_runs(st: Stream) -> list[tuple[int, int]]:
    runs, i, n = [], 0, len(st.text)
    while i < n:
        if st.bold[i]:
            j = i
            while j < n and st.bold[j]:
                j += 1
            runs.append((i, j))
            i = j
        else:
            i += 1
    return runs


def upper_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    return sum(c.isupper() for c in letters) / len(letters) if letters else 0.0


def section_of(heading: str) -> str | None:
    h = heading.upper()
    return next((kind for key, kind in SECTION_KEYWORDS if key in h), None)


@dataclass
class _Marker:
    start: int  # where the marker text begins
    end: int  # where the turn text (or the next thing) begins
    kind: str  # label | question | heading | subheading
    text: str
    qno: int | None = None


def find_markers(st: Stream, label_max: int, heading_upper: float) -> list[_Marker]:
    line_starts = set(st.line_start)
    markers: list[_Marker] = []
    for a, b in bold_runs(st):
        # A run may start with a bold space or line break left over from the previous line, or in the
        # middle of a line (the bold tail of a stage direction): start it at its first line start.
        while a < b and st.text[a] in " \t\n":
            a += 1
        k = a
        while k > 0 and st.text[k - 1] in " \t":
            k -= 1
        if k not in line_starts:
            nl = st.text.find("\n", a, b)
            if nl == -1:
                continue
            a = nl + 1
            while a < b and st.text[a] in " \t\n":
                a += 1
        if a >= b:
            continue
        lines = st.text[a:b].split("\n")
        after = st.text[b : b + 2]
        ends_label = lines[-1].rstrip().endswith(":") or after.lstrip().startswith(":")
        is_question = bool(re.search(r"\[.+\]\s*$", lines[-1])) and st.text[
            b : b + 12
        ].lstrip().lower().startswith(("minta", "meminta", "bertanya"))
        # Where does the label start inside the run? The latest line that begins like a label and from
        # which the brackets balance. Lines above it are headings, subheadings, stage lines or numbers.
        cut = len(lines)
        if ends_label or is_question:
            for k in range(len(lines) - 1, -1, -1):
                tail = "\n".join(lines[k:])
                if LABEL_START.match(lines[k].strip()) and tail.count("[") == tail.count("]"):
                    cut = k
                    break
        offset, qno = a, None
        for line in lines[:cut]:
            t = line.strip()
            if q := _QNUM.match(t):
                qno = int(q.group(1))
            elif t and not (t.startswith("[") and t.endswith("]")) and not t.endswith(":"):
                whole = (
                    cut < len(lines) or st.text[b : (st.text.find("\n", b) + 1 or len(st.text))].strip() == ""
                )
                if whole:
                    kind = "heading" if upper_ratio(t) >= heading_upper else "subheading"
                    markers.append(_Marker(offset, offset + len(line), kind, t))
            offset += len(line) + 1
        if cut == len(lines):
            continue
        body = " ".join("\n".join(lines[cut:]).split())
        if is_question and not ends_label:
            if qno is None:
                q = re.search(r"(\d{1,3})\.\s*$", st.text[max(0, offset - 12) : offset])
                qno = int(q.group(1)) if q else None
            markers.append(_Marker(offset, b, "question", body, qno))
            continue
        label_text = body.rstrip(":").strip()
        end = b if body.endswith(":") else b + after.index(":") + 1
        if 1 < len(label_text) <= label_max and any(c.isalpha() for c in label_text):
            markers.append(_Marker(offset, end, "label", label_text))
    return markers


def _clean_text(st: Stream, a: int, b: int) -> tuple[str, list[str]]:
    """Turn text between offsets, italic [stage directions] removed and returned separately."""
    raw = st.text[a:b]
    stages: list[str] = []
    out = []
    last = 0
    for m in _STAGE.finditer(raw):
        s, e = a + m.start(), a + m.end()
        if sum(st.italic[s:e]) >= (e - s) // 2:  # mostly italic: a stage direction, not speech
            stages.append(" ".join(m.group()[1:-1].split()))
            out.append(raw[last : m.start()])
            last = m.end()
    out.append(raw[last:])
    text = "".join(out)
    text = re.sub(r"(?m)^\s*\d{1,3}\.\s*$", "", text)  # oral question numbers on their own line
    text = re.sub(r"-\n(?=[a-z])", "-", text)  # "mana-\nmana" -> "mana-mana"
    return " ".join(text.split()), stages


def segment(pages: list[Page], label_max: int, heading_upper: float) -> tuple[list[Turn], list[str]]:
    """Speaker turns of the debate pages, plus the preamble's stage directions (before the first label)."""
    st = flatten(pages[debate_start(pages) :])
    markers = sorted(find_markers(st, label_max, heading_upper), key=lambda m: m.start)
    turns: list[Turn] = []
    section, heading, sub = "other", None, None
    qno: int | None = None  # printed number of the current oral question
    group: int | None = None  # running number of the current question (oral or minister's question time)
    groups = 0
    preamble: list[str] = []
    for i, m in enumerate(markers):
        nxt = markers[i + 1].start if i + 1 < len(markers) else len(st.text)
        if m.kind in ("heading", "subheading"):
            if m.kind == "heading":
                sec = section_of(m.text)
                if sec:
                    section, heading, sub, qno, group = sec, m.text, None, None, None
            else:
                sub = m.text
            continue
        text, stages = _clean_text(st, m.end, nxt)
        label = parse_label(m.text)
        if m.kind == "question":
            qno, groups = m.qno, groups + 1
            group = groups
            kind = "written_question"
        else:
            kind = "speech" if text else "action"  # "action": only a stage direction, e.g. [Bangun]
        in_questions = section in ("oral_questions", "minister_question_time")
        t = Turn(seq=len(turns), kind=kind, label=label, text=text, section=section, section_heading=heading,
                 subheading=sub, question_no=qno if section == "oral_questions" else None,
                 question_group=group if in_questions else None,
                 stage_directions=stages, page_start=st.page[m.start], page_end=st.page[max(m.start, nxt - 1)],
                 char_start=m.start, char_end=nxt)  # fmt: skip
        t.times = [tm for off, tm in st.times if m.start <= off < nxt]
        turns.append(t)
    if markers:
        preamble = _clean_text(st, 0, markers[0].start)[1]
    return turns, preamble
