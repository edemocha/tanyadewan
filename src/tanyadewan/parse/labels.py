"""Speaker labels: the bold text before the colon that opens a turn.

Tuan Yang di-Pertua                      the Speaker (who, comes from the attendance list)
Timbalan Yang di-Pertua [Name]           a Deputy Speaker, name in brackets
Name [Constituency]                      an MP
Menteri … [Name]                         a minister: role outside, NAME in brackets
Name                                     someone already introduced this sitting
Seorang Ahli / Beberapa Ahli             "a Member" / "several Members": never attributed to anyone
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

# A label whose text before the brackets starts with one of these is "Role [Name]".
ROLE_PREFIXES = (
    "timbalan yang di-pertua", "yang di-pertua", "tuan yang di-pertua", "perdana menteri", "timbalan perdana menteri",
    "menteri", "timbalan menteri", "setiausaha parlimen", "ketua pembangkang", "ketua whip", "peguam negara",
    "tuan pengerusi", "puan pengerusi", "pengerusi", "setiausaha",
)  # fmt: skip
# Roles that chair the sitting (or the committee stage); a bare label names no one.
CHAIR_ROLES = (
    "tuan yang di-pertua",
    "timbalan yang di-pertua",
    "tuan pengerusi",
    "puan pengerusi",
    "pengerusi",
)
# How a speaker label can begin. Used to find where a label starts inside a longer bold run.
LABEL_START = re.compile(
    r"^(Tuan|Puan|Cik|Dato'?|Datuk|Datin|Tan Sri|Toh Puan|Tun|Dr\.?|Senator|Yang|Ir\.|Ts\.|Haji|Hajah|Ustaz|"
    r"Ustazah|Prof\.?|Kapten|Mejar|Seorang|Beberapa|Timbalan|Menteri|Perdana|Setiausaha|Ketua|Peguam|"
    r"Pengerusi|Sahabat|YB|Y\.B\.|OCR)\b"  # "OCR tidak dapat dibaca": an unreadable-line boundary
)
SPEAKER_OF_HOUSE = ("tuan yang di-pertua", "yang di-pertua", "yang di-pertua dewan rakyat")
UNATTRIBUTED = (
    "seorang ahli",
    "beberapa ahli",
    "ahli-ahli",
    "beberapa orang ahli",
    "seorang ahli yang berhormat",
)


@dataclass(frozen=True)
class Label:
    raw: str
    name: str | None
    constituency: str | None
    role: str | None
    unattributed: bool = False
    unreadable: bool = False  # an OCR line too damaged to read: a boundary with no speaker


_APOSTROPHES = str.maketrans({c: "'" for c in "’‘ʼ`´"})


def clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text.translate(_APOSTROPHES)).strip(" :")
    return re.sub(r"(?i)\byang\W{0,2}di\W{0,2}pertua\b", "Yang di-Pertua", text)  # "Yang'di-Pertua" typo


def is_role(text: str) -> bool:
    t = text.lower()
    return any(t == p or t.startswith(p + " ") or t.startswith(p + ",") for p in ROLE_PREFIXES)


_HONORIFIC_BEFORE_ROLE = re.compile(r"^(?:Yang Amat Berhormat|Yang Berhormat|YAB|YB|Y\.B\.)\s+", re.I)


def _without_honorific_before_role(text: str) -> str:
    """"Yang Amat Berhormat Perdana Menteri … [Name]" is the role label "Perdana Menteri … [Name]". An honorific
    before a person's name ("Yang Berhormat Tuan X [Seat]") is left alone: only a role makes it droppable."""
    m = _HONORIFIC_BEFORE_ROLE.match(text)
    if m is None:
        return text
    rest = text[m.end() :]
    head = re.match(r"^(.*?)\s*\[", rest)
    return rest if is_role(clean(head.group(1) if head else rest)) else text


def parse_label(raw: str) -> Label:
    text = clean(raw)
    stripped = _without_honorific_before_role(text)
    if stripped != text:
        return replace(parse_label(stripped), raw=text)
    low = text.lower()
    if low == "ocr tidak dapat dibaca":
        return Label(text, None, None, None, unreadable=True)
    if low in UNATTRIBUTED:
        return Label(text, None, None, None, unattributed=True)
    if low in SPEAKER_OF_HOUSE:
        return Label(text, None, None, "Tuan Yang di-Pertua")
    m = re.match(r"^(.*?)\s*\[(.+)\]$", text)
    if m:
        outer, inner = clean(m.group(1)), clean(m.group(2))
        if is_role(outer):
            # "Menteri …, Datuk Seri Haji Mohamad bin Sabu [Kota Raja]": role, name, THEN the seat
            split = [c for c in re.finditer(r",\s*", outer) if LABEL_START.match(outer[c.end() :])]
            if split and not is_role(outer[split[-1].end() :]):
                c = split[-1]
                return Label(text, outer[c.end() :].strip(), inner, outer[: c.start()].strip())
            return Label(text, inner, None, outer)
        return Label(text, outer, inner, None)
    if is_role(text):
        return Label(text, None, None, text)
    return Label(text, text, None, None)
