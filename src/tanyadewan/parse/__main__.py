"""Parse downloaded Hansard PDFs into speaker turns and build the speaker registry.

    uv run python -m tanyadewan.parse                 # every downloaded sitting
    uv run python -m tanyadewan.parse --doc DR-2023-03-14

Two passes: parse every sitting (turns + attendance), build the registry from all attendance lists
and labels, then resolve each turn to a speaker ID. Outputs (gitignored):
    data/processed/turns/<doc_id>.jsonl   data/processed/speakers.json   data/processed/parse_report.json
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tanyadewan.config import ROOT, load_config
from tanyadewan.fetch.records import DocumentRecord, load_records
from tanyadewan.parse.attendance import AttendanceEntry, parse_attendance
from tanyadewan.parse.extract import Page, debate_start, extract_pages
from tanyadewan.parse.labels import CHAIR_ROLES
from tanyadewan.parse.lang import dominant_language
from tanyadewan.parse.segment import Turn, segment
from tanyadewan.speakers.registry import Registry, chair_from_stage

RESOLVED = {
    "label_constituency",
    "label_name",
    "label_name_seat_unmatched",
    "label_fuzzy",
    "attendance_role",
    "chair_named",
    "chair_carried",
}


@dataclass
class Parsed:
    doc: DocumentRecord
    pages: list[Page]
    turns: list[Turn]
    attendance: list[AttendanceEntry]
    preamble: list[str]


def parse_document(doc: DocumentRecord) -> Parsed:
    cfg = load_config().parse
    pages = extract_pages(
        ROOT / str(doc.local_path), cfg.header_scan_lines, load_config().ocr, cfg.label_max_chars
    )
    front = pages[: debate_start(pages)]
    attendance = parse_attendance([line.text for p in front for line in p.lines])
    turns, preamble = segment(pages, cfg.label_max_chars, cfg.heading_min_upper_ratio)
    return Parsed(doc, pages, turns, attendance, preamble)


def speaker_key(t: Turn, sid: str | None) -> str:
    return sid or t.label.raw


def resolve_and_write(parsed: list[Parsed], registry: Registry, out_dir: Path) -> dict[str, dict[str, Any]]:
    cfg = load_config().parse
    out_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, dict[str, Any]] = {}
    for p in parsed:
        chair: str | None = None
        speaker_name = next(
            (e.name for e in p.attendance if e.role and e.role.lower().startswith("yang di-pertua")), None
        )
        for stage in p.preamble:
            name, is_chair = chair_from_stage(stage)
            chair = name or (speaker_name if is_chair else chair)
        rows = []
        for t in p.turns:
            res = registry.resolve(t.label, p.attendance, chair, p.doc.sitting_date)
            rows.append((t, res))
            role = (t.label.role or "").lower()
            if t.label.name and any(role.startswith(c) for c in CHAIR_ROLES):
                chair = t.label.name  # a named chair label also tells us who is in the chair
            for stage in t.stage_directions:
                name, is_chair = chair_from_stage(stage)
                if is_chair:
                    chair = name or speaker_name
        labels = {p.pages[i].number: p.pages[i].label for i in range(len(p.pages))}
        ocr_pages = {pg.number for pg in p.pages if pg.ocr}
        lines: list[dict[str, Any]] = []
        methods: collections.Counter[str] = collections.Counter()
        for i, (t, res) in enumerate(rows):
            key = speaker_key(t, res.speaker_id)
            prev_key = speaker_key(rows[i - 1][0], rows[i - 1][1].speaker_id) if i else None
            next_key = speaker_key(rows[i + 1][0], rows[i + 1][1].speaker_id) if i + 1 < len(rows) else None
            is_chair = any((t.label.role or "").lower().startswith(c) for c in CHAIR_ROLES)
            interjection = t.label.unattributed or (
                t.kind == "speech" and not is_chair and len(t.text) <= cfg.interjection_max_chars
                and prev_key is not None and prev_key == next_key and prev_key != key
            )  # fmt: skip
            methods[res.method] += 1
            lines.append({
                "turn_id": f"{p.doc.doc_id}:{t.seq:04d}", "doc_id": p.doc.doc_id, "sitting_date": p.doc.sitting_date,
                "seq": t.seq, "kind": t.kind, "speaker_raw": t.label.raw, "speaker_name": t.label.name,
                "constituency": t.label.constituency, "role": t.label.role, "unattributed": t.label.unattributed,
                "speaker_id": res.speaker_id, "resolution": res.method, "is_interjection": interjection,
                "text": t.text, "stage_directions": t.stage_directions, "times": t.times, "section": t.section,
                "section_heading": t.section_heading, "subheading": t.subheading, "question_no": t.question_no,
                "question_group": t.question_group, "page_start": t.page_start, "page_end": t.page_end,
                "page_label_start": labels.get(t.page_start), "char_start": t.char_start, "char_end": t.char_end,
                "lang": dominant_language(t.text, cfg.lang_min_stopwords, cfg.lang_mixed_share),
                "is_draft": p.doc.is_draft, "source_url": p.doc.source_url,
                "ocr": any(n in ocr_pages for n in range(t.page_start, t.page_end + 1)),
            })  # fmt: skip
        (out_dir / f"{p.doc.doc_id}.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in lines), encoding="utf-8"
        )
        no_text = [
            pg.number
            for pg in p.pages[debate_start(p.pages) :]
            if not any(ln.text.strip() for ln in pg.lines)
        ]
        report[p.doc.doc_id] = {
            "turns": len(lines), "resolution": dict(methods), "attendance_entries": len(p.attendance),
            "unattributed": sum(r["unattributed"] for r in lines), "interjections": sum(r["is_interjection"] for r in lines),
            "pages": len(p.pages), "debate_pages_without_text": no_text, "is_draft": p.doc.is_draft,
            "ocr_pages": len(ocr_pages), "ocr_unreadable_lines": sum(r["resolution"] == "ocr_unreadable" for r in lines),
        }  # fmt: skip
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--doc", action="append", default=[], help="only these doc_ids (the registry still uses all)"
    )
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    cfg = load_config()
    docs = [
        d
        for d in load_records(cfg.paths.documents).values()
        if d.local_path and (ROOT / d.local_path).exists()
    ]
    print(f"Reading {len(docs)} sittings. Every word, every [Tepuk]. Grab a teh tarik.")
    parsed = []
    for d in sorted(docs, key=lambda d: d.sitting_date):
        parsed.append(parse_document(d))
        print(
            f"  {d.doc_id}: {len(parsed[-1].turns):4d} turns, {len(parsed[-1].attendance):3d} attendance entries"
        )

    registry = Registry()
    for p in parsed:  # attendance first: it is the authoritative source of names and seats
        registry.add_attendance(p.attendance, p.doc.sitting_date)

    targets = [p for p in parsed if not args.doc or p.doc.doc_id in args.doc]
    report = resolve_and_write(targets, registry, cfg.parse.turns_dir)
    cfg.parse.speakers.write_text(
        json.dumps(registry.to_list(), ensure_ascii=False, indent=1), encoding="utf-8"
    )
    unresolved = dict(sorted(registry.unresolved_names.items(), key=lambda kv: -kv[1]))
    summary = {
        "sittings": report,
        "speakers": len(registry.by_core),
        "unresolved_label_names": unresolved,
        "seat_conflicts": registry.conflicts,
    }
    cfg.parse.report.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    totals: collections.Counter[str] = collections.Counter()
    for r in report.values():
        totals.update(r["resolution"])
    n = sum(totals.values())
    resolved = sum(v for k, v in totals.items() if k in RESOLVED)
    print(f"Done. {n} turns, {resolved / max(n, 1):.1%} resolved to a speaker. {len(registry.by_core)} speakers, "
          f"{len(unresolved)} label names unresolved (see report), {len(registry.conflicts)} seat conflicts.")  # fmt: skip
    print("  by method:", dict(totals.most_common()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
