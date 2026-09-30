"""Who each turn belongs to.

Identities come ONLY from the attendance lists printed in each Hansard (role, name, seat per sitting)
plus the curated aliases in speakers/aliases.yaml. Labels never create a person: a label that matches
no one stays unresolved and is listed for review. Misattribution is the worst failure (CLAUDE.md), so
"unresolved" is always preferred to a guess.

Resolution methods, recorded on every turn (in order of strength):
  label_constituency  core name matches, and that person held the labelled seat on that date
  label_name          core name matches exactly one person present in this sitting (or in the registry)
  label_fuzzy         spelling variant of exactly one person in this sitting's attendance list: near-identical
                      spelling ("Hamdan"/"Hamzan") or one name's words contained in the other's; if the label
                      names a seat, that person must hold it on that date
  attendance_role     role-only label ("Tuan Yang di-Pertua", "Menteri X") -> the one person holding that
                      role in this sitting's attendance list
  chair_named         a chair label that carries the chair's name ("Timbalan Yang di-Pertua [Name]")
  chair_carried       a bare chair label ("Tuan Pengerusi") -> the chair most recently named in this sitting
Unresolved reasons: unattributed, unknown_name, ambiguous_name, seat_mismatch, no_chair_named, unknown_role.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

import yaml

from tanyadewan.parse.attendance import AttendanceEntry
from tanyadewan.parse.labels import CHAIR_ROLES, Label
from tanyadewan.speakers.names import aliases, core_name, slug

FUZZY_RATIO = 0.85  # near-identical spelling
FUZZY_MIN_SHARED_TOKENS = 2  # for containment ("Hannah Yeoh" within "Hannah Yeoh Tseow Suan")
ALIASES_FILE = Path(__file__).with_name("aliases.yaml")


def _norm(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").lower().translate(str.maketrans("’ʼ", "''"))).strip()


def _seat(text: str | None) -> str:
    """Seat names compared without punctuation: "Kulim-Bandar Baharu" == "Kulim Bandar Baharu"."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).split())


@dataclass
class Speaker:
    speaker_id: str
    core: str
    names: dict[str, int] = field(default_factory=dict)  # printed name -> times seen
    constituencies: dict[str, list[str]] = field(default_factory=dict)  # seat -> [first_seen, last_seen]
    roles: dict[str, list[str]] = field(default_factory=dict)
    label_variants: dict[str, int] = field(default_factory=dict)  # label spellings resolved to this person

    @property
    def name(self) -> str:
        return max(self.names.items(), key=lambda kv: kv[1])[0] if self.names else self.core

    def to_dict(self) -> dict[str, object]:
        return {
            "speaker_id": self.speaker_id, "name": self.name, "core_name": self.core,
            "name_variants": sorted(self.names), "label_variants": sorted(self.label_variants),
            "constituencies": [{"constituency": c, "first_seen": d[0], "last_seen": d[1]}
                               for c, d in sorted(self.constituencies.items())],
            "roles": [{"role": r, "first_seen": d[0], "last_seen": d[1]} for r, d in sorted(self.roles.items())],
        }  # fmt: skip


def _seen(span: dict[str, list[str]], key: str, when: str) -> None:
    fl = span.setdefault(key, [when, when])
    fl[0], fl[1] = min(fl[0], when), max(fl[1], when)


def similar(a: str, b: str, min_shared: int = FUZZY_MIN_SHARED_TOKENS) -> bool:
    """Near-identical spelling, or one name's words all contained in the other's (at least min_shared
    words; 1 only where a shared seat already narrows it to one person: "Nancy" / "Nancy Shukri")."""
    if not a or not b:
        return False
    ta, tb = set(a.split()), set(b.split())
    if min(len(ta), len(tb)) >= min_shared and (ta <= tb or tb <= ta):
        return True
    return SequenceMatcher(None, a, b).ratio() >= FUZZY_RATIO


@dataclass
class Resolution:
    speaker_id: str | None
    method: str  # a method (resolved) or a reason (unresolved)


class Registry:
    def __init__(self, alias_file: Path | None = ALIASES_FILE) -> None:
        self.by_core: dict[str, Speaker] = {}
        self.alias_to_core: dict[str, str] = {}  # other core forms (after "@", curated aliases) -> core
        self.seats: dict[tuple[str, str], set[str]] = {}  # (seat, date) -> cores holding it
        self.conflicts: list[str] = []
        self.unresolved_names: dict[str, int] = {}
        self._ids: set[str] = set()
        self._curated: dict[str, str] = {}
        if alias_file and alias_file.exists():
            data = yaml.safe_load(alias_file.read_text(encoding="utf-8")) or {}
            for canonical, variants in (data.get("aliases") or {}).items():
                for v in variants or []:
                    self._curated[core_name(v)] = core_name(canonical)

    # ── building (attendance only) ─────────────────────────────────────────
    def _canonical(self, core: str) -> str:
        return self._curated.get(core, self.alias_to_core.get(core, core))

    def _speaker(self, core: str) -> Speaker:
        core = self._canonical(core)
        sp = self.by_core.get(core)
        if sp is None:
            sid = base = slug(core)
            n = 2
            while sid in self._ids:
                sid, n = f"{base}-{n}", n + 1
            self._ids.add(sid)
            sp = self.by_core[core] = Speaker(sid, core)
        return sp

    def add_attendance(self, entries: Iterable[AttendanceEntry], when: str) -> None:
        for e in entries:
            core = self._canonical(core_name(e.name))
            if not core:
                continue
            if core not in self.by_core and e.constituency:
                # Another printing of someone already known for this seat ("Kulasegaran" /
                # "Kulasegaran a/l V. Murugeson"). A by-election winner has an unrelated name: no merge.
                seat = _seat(e.constituency)
                same_seat = {c for (s, _), cores in self.seats.items() if s == seat for c in cores}
                match = [c for c in same_seat if similar(core, c, min_shared=1)]
                if len(match) == 1:
                    self.alias_to_core[core] = match[0]
                    core = match[0]
            sp = self._speaker(core)
            for a in aliases(e.name):
                self.alias_to_core.setdefault(a, sp.core)
            sp.names[e.name] = sp.names.get(e.name, 0) + 1
            if e.constituency:
                _seen(sp.constituencies, e.constituency, when)
                holders = self.seats.setdefault((_seat(e.constituency), when), set())
                holders.add(sp.core)
            if e.role:
                _seen(sp.roles, e.role, when)
        # Two people listed for one seat on one date means the printed list is corrupt (seen on 2023-11-20:
        # several seats replaced by "… Selangor"). Don't learn seats from it: drop that seat for that date,
        # and drop the seat from a person's history if this corrupt list was the only place it appeared.
        for (seat, day), holders in list(self.seats.items()):
            if day != when or len(holders) < 2:
                continue
            self.conflicts.append(
                f"{when}: seat '{seat}' listed for {sorted(holders)}; ignored for this sitting"
            )
            del self.seats[(seat, day)]
            for core in holders:
                spans = self.by_core[core].constituencies
                for name in [n for n, (a, b) in spans.items() if _seat(n) == seat and a == b == when]:
                    del spans[name]

    # ── resolving ───────────────────────────────────────────────────────────
    def resolve(
        self, label: Label, sitting: list[AttendanceEntry], chair: str | None, when: str
    ) -> Resolution:
        if label.unattributed:
            return Resolution(None, "unattributed")
        if label.unreadable:
            return Resolution(None, "ocr_unreadable")
        role = _norm(label.role)
        is_chair_role = bool(role) and any(role.startswith(c) for c in CHAIR_ROLES)
        if label.name:
            res = self._by_name(label, sitting, when)
            if res.speaker_id and is_chair_role:
                res.method = "chair_named"
            if res.speaker_id is None:
                self.unresolved_names[label.raw] = self.unresolved_names.get(label.raw, 0) + 1
            else:
                sp = next(s for s in self.by_core.values() if s.speaker_id == res.speaker_id)
                sp.label_variants[label.name] = sp.label_variants.get(label.name, 0) + 1
            return res
        if role in ("tuan yang di-pertua", "yang di-pertua"):
            return self._one([e for e in sitting if e.role and _norm(e.role).startswith("yang di-pertua")])
        if is_chair_role:
            if chair is None:
                return Resolution(None, "no_chair_named")
            holder = self.by_core.get(self._canonical(core_name(chair)))
            return (
                Resolution(holder.speaker_id, "chair_carried") if holder else Resolution(None, "unknown_name")
            )
        if role:
            return self._one([e for e in sitting if e.role and _norm(e.role) == role])
        return Resolution(None, "unknown_name")

    def _by_name(self, label: Label, sitting: list[AttendanceEntry], when: str) -> Resolution:
        assert label.name is not None
        core = self._canonical(core_name(label.name))
        seat = _seat(label.constituency) if label.constituency else None
        holders = self.seats.get((seat, when), set()) if seat else set()
        sp = self.by_core.get(core)
        if sp is not None:
            if seat is None:
                return Resolution(sp.speaker_id, "label_name")
            if sp.core in holders or (not holders and seat in {_seat(c) for c in sp.constituencies}):
                return Resolution(sp.speaker_id, "label_constituency")
            if not holders:  # exact name, but nobody holds that seat: a typo in the seat ("Kuala fasal")
                return Resolution(sp.speaker_id, "label_name_seat_unmatched")
            return Resolution(None, "seat_mismatch")  # the seat belongs to someone else: never guess
        # Spelling variant: only among the people in THIS sitting's attendance list.
        present = {self._canonical(core_name(e.name)) for e in sitting}
        candidates = {c for c in present if similar(core, c)}
        if seat is not None and holders:
            candidates &= holders
        if len(candidates) == 1:
            return Resolution(self.by_core[candidates.pop()].speaker_id, "label_fuzzy")
        return Resolution(None, "ambiguous_name" if candidates else "unknown_name")

    def _one(self, entries: list[AttendanceEntry]) -> Resolution:
        cores = {self._canonical(core_name(e.name)) for e in entries}
        if len(cores) != 1:
            return Resolution(None, "unknown_role" if not cores else "ambiguous_name")
        sp = self.by_core.get(cores.pop())
        return Resolution(sp.speaker_id, "attendance_role") if sp else Resolution(None, "unknown_name")

    def to_list(self) -> list[dict[str, object]]:
        return [sp.to_dict() for sp in sorted(self.by_core.values(), key=lambda s: s.speaker_id)]


_CHAIR_STAGE = re.compile(r"^(.*?)\s*(?:\((.+?)\))?\s*mempengerusikan\b", re.I)


def chair_from_stage(stage: str) -> tuple[str | None, bool]:
    """'[Timbalan Yang di-Pertua (Dato' X) mempengerusikan Mesyuarat]' -> ("Dato' X", True).
    '[Tuan Yang di-Pertua mempengerusikan Mesyuarat]' -> (None, True): the Speaker, named via attendance.
    Anything else -> (None, False)."""
    m = _CHAIR_STAGE.match(" ".join(stage.split()))
    if not m:
        return None, False
    return (m.group(2).strip() if m.group(2) else None), True
