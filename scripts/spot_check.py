"""Verify attribution by eye: random turns printed next to the PDF page they came from.

    uv run python scripts/spot_check.py --n 20
    uv run python scripts/spot_check.py --n 10 --method label_fuzzy      # review one resolution method
    uv run python scripts/spot_check.py --n 10 --method chair_carried
    uv run python scripts/spot_check.py --n 10 --unresolved
    uv run python scripts/spot_check.py --turn DR-2023-03-14:0042

For each turn: who the parser says spoke (and how it decided), the start of the text, then the raw
page with the speaker line marked ">>>". Output is local only (Hansard text is not redistributed).
"""

from __future__ import annotations

import argparse
import json
import random
import sys

import pymupdf

from tanyadewan.config import ROOT, load_config
from tanyadewan.fetch.records import load_records
from tanyadewan.parse.__main__ import RESOLVED

EXCERPT = 400


def load_turns(doc_filter: str | None) -> list[dict[str, object]]:
    rows = []
    for path in sorted(load_config().parse.turns_dir.glob("*.jsonl")):
        if doc_filter and path.stem != doc_filter:
            continue
        rows += [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows


def page_text(local_path: str, page: int) -> list[str]:
    with pymupdf.open(ROOT / local_path) as doc:
        return doc[page - 1].get_text("text").splitlines()


def show(turn: dict[str, object], docs: dict[str, object]) -> None:
    doc = docs[str(turn["doc_id"])]
    who = turn["speaker_id"] or f"UNRESOLVED ({turn['resolution']})"
    print("=" * 100)
    print(f"{turn['turn_id']}  {turn['sitting_date']}  {turn['section']}  pdf page {turn['page_start']}"
          f" (printed {turn['page_label_start']})  kind={turn['kind']}  lang={turn['lang']}")  # fmt: skip
    print(f"label     : {turn['speaker_raw']}")
    print(f"parsed as : name={turn['speaker_name']!r} seat={turn['constituency']!r} role={turn['role']!r}")
    print(
        f"speaker   : {who}   via {turn['resolution']}"
        + ("   [INTERJECTION]" if turn["is_interjection"] else "")
    )
    if turn["stage_directions"]:
        print(f"stage     : {turn['stage_directions']}")
    text = str(turn["text"])
    print(f"text      : {text[:EXCERPT]}{' …' if len(text) > EXCERPT else ''}")
    print(f"--- raw page {turn['page_start']} of {doc.filename} (the speaker line is marked >>>)")  # type: ignore[attr-defined]
    first = str(turn["speaker_raw"]).split("[")[0].strip()[:25]
    marked = False
    for line in page_text(str(doc.local_path), int(turn["page_start"])):  # type: ignore[attr-defined]
        hit = not marked and first and first in line
        print((">>> " if hit else "    ") + line.rstrip())
        marked = marked or bool(hit)
    if not marked:
        print("    (label starts on a previous line or page; see the page above)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=None, help="repeat the same sample")
    ap.add_argument("--method", help="only turns resolved by this method (e.g. label_fuzzy, chair_carried)")
    ap.add_argument("--unresolved", action="store_true")
    ap.add_argument("--doc", help="only this sitting, e.g. DR-2023-03-14")
    ap.add_argument("--turn", help="one specific turn_id")
    ap.add_argument("--include-empty", action="store_true", help="include action turns ([Bangun] only)")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    docs = load_records(load_config().paths.documents)
    turns = load_turns(args.doc)
    if args.turn:
        turns = [t for t in turns if t["turn_id"] == args.turn]
    if args.method:
        turns = [t for t in turns if t["resolution"] == args.method]
    if args.unresolved:
        turns = [t for t in turns if t["resolution"] not in RESOLVED]
    if not args.include_empty:
        turns = [t for t in turns if t["text"]] or turns
    if not turns:
        print("No turns match. Run `uv run python -m tanyadewan.parse` first, or loosen the filters.")
        return 1
    rng = random.Random(args.seed)
    sample = turns if args.turn else rng.sample(turns, min(args.n, len(turns)))
    for t in sorted(sample, key=lambda t: str(t["turn_id"])):
        show(t, docs)
    print("=" * 100)
    print(f"{len(sample)} of {len(turns)} matching turns shown. Check: is the marked line the same speaker,"
          " and does the text start where their speech starts?")  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
