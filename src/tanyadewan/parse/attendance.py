"""Attendance lists in the front matter: the authoritative role / name / constituency per sitting.

    Ahli-ahli Yang Hadir:
    1.
    Yang di-Pertua Dewan Rakyat, Tan Sri Dato' (Dr.) Johari bin Abdul
    2.
    Perdana Menteri dan Menteri Kewangan, Dato' Seri Anwar bin Ibrahim (Tambun)
    ...
    Ahli-Ahli Yang Tidak Hadir:
    Ahli-Ahli Yang Tidak Hadir Di Bawah Peraturan Mesyuarat 91:

Roles can contain commas ("Menteri Sumber Asli, Alam Sekitar dan Perubahan Iklim, Tuan …"), so the
role/name split is at the last comma followed by an honorific.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from tanyadewan.parse.labels import clean, is_role

# Where a name starts after a role. ("Yang" is left out: roles contain "Yang di-Pertua".)
HONORIFIC_START = re.compile(
    r"^(Tuan|Puan|Cik|Dato'?|Datuk|Datin|Tan Sri|Toh Puan|Tun|Dr\.?|Senator|Ir\.|Ts\.|Haji|Hajah|Ustaz|"
    r"Ustazah|Prof\.?|Kapten|Komander|Mejar|Jeneral|Laksamana|Sahabat)\b"
)
_STATUS = [  # list titles; case and the trailing ":" vary, "(Samb/-)" marks a continuation
    (re.compile(r"senator.*turut hadir", re.I), "present_senator"),
    (re.compile(r"tidak hadir.*peraturan mesyuarat\s*91", re.I), "absent_po91"),
    (re.compile(r"yang tidak hadir", re.I), "absent"),
    (re.compile(r"yang hadir", re.I), "present"),
    (re.compile(r"kehadiran ahli", re.I), "present"),  # first sitting: "KEHADIRAN AHLI-AHLI PARLIMEN"
    (re.compile(r"digantung", re.I), "suspended"),
]
# Entry numbers: "1." on its own line (most sittings) or inline "1 Perdana Menteri …" (some 2023-2026).
_NUMBER = re.compile(r"(?<![\w.(/-])(\d{1,3})\.?(?=\s|$)")
_TRAILING_PAREN = re.compile(r"^(.*)\(([^()]+)\)\s*$")
NOT_CONSTITUENCY = {"dr.", "dr", "prof.", "prof"}


@dataclass(frozen=True)
class AttendanceEntry:
    status: str  # present | absent | absent_po91
    raw: str
    role: str | None
    name: str
    constituency: str | None


def parse_entry(raw: str, status: str) -> AttendanceEntry:
    text = clean(raw)
    constituency = None
    m = _TRAILING_PAREN.match(text)
    if m and m.group(2).strip().lower() not in NOT_CONSTITUENCY:
        text, constituency = m.group(1).strip(" ,"), clean(m.group(2))
    role = None
    if is_role(text):
        cut = None
        for c in re.finditer(r",\s*", text):
            if HONORIFIC_START.match(text[c.end() :]):
                cut = c
        if cut is not None:
            role, text = text[: cut.start()].strip(), text[cut.end() :].strip()
        else:
            # Printed without the comma: "Timbalan Menteri … (… Institusi) Tuan M. Kulasegaran".
            first = next((m for m in re.finditer(r"(?<=[\s)])(?=\S)", text) if HONORIFIC_START.match(text[m.end():])),
                         None)  # fmt: skip
            if first is not None:
                role, text = text[: first.start()].strip(" ,"), text[first.end() :].strip()
            elif "," in text:  # no honorific at all: the last comma
                last = list(re.finditer(r",\s*", text))[-1]
                role, text = text[: last.start()].strip(), text[last.end() :].strip()
    return AttendanceEntry(status, clean(raw), role, text, constituency)


def _title(line: str) -> str | None:
    t = line.strip()
    if len(t) > 110 or _NUMBER.match(t):
        return None
    return next((s for pat, s in _STATUS if pat.search(t)), None)


_MONTHS = "januari|februari|mac|april|mei|jun|julai|ogos|september|oktober|november|disember"
# The sitting's date printed above the list ("19 DISEMBER 2022 (ISNIN)"): its day number is not an entry number.
_DATE_HEADER = re.compile(rf"\d{{1,2}}\s+(?:{_MONTHS})\s+\d{{4}}(?:\s*\([^)]*\))?", re.I)


def split_numbered(text: str) -> list[str]:
    """Split a list on SEQUENTIAL numbers only (1, 2, 3 …), so a number inside a role title
    ("P.M. 14") can't start a new entry. A continued list may start above 1."""
    text = text.lstrip()
    if (header := _DATE_HEADER.match(text)) is not None:
        text = text[header.end() :]
    cuts: list[tuple[int, int]] = []  # (start of number, start of entry text)
    expected: int | None = None
    for m in _NUMBER.finditer(text):
        n = int(m.group(1))
        if (expected is None and not text[: m.start()].strip()) or n == expected:
            cuts.append((m.start(), m.end()))
            expected = n + 1
    entries = []
    for i, (_, begin) in enumerate(cuts):
        end = cuts[i + 1][0] if i + 1 < len(cuts) else len(text)
        chunk = " ".join(text[begin:end].split())
        if chunk:
            entries.append(chunk)
    return entries


def parse_attendance(lines: list[str]) -> list[AttendanceEntry]:
    """lines: front-matter text lines in reading order."""
    blocks: list[tuple[str, list[str]]] = []  # (status, lines); a "(Samb/-)" title continues the same status
    status: str | None = None
    for line in lines:
        t = line.strip()
        if not t:
            continue
        new_status = _title(t)
        if new_status:
            status = new_status
            blocks.append((status, []))
            continue
        if status is None:
            continue
        if t.endswith(":") and len(t) < 110:  # any other list title ends the attendance lists
            status = None
            continue
        blocks[-1][1].append(t)
    entries: list[AttendanceEntry] = []
    for st, block_lines in blocks:
        for chunk in split_numbered(" ".join(block_lines)):
            entries.append(parse_entry(chunk, st))
    return entries
