"""Export the small public metadata the hosted backend needs into backend/seed/ (committed to git).

    uv run python scripts/export_public_seed.py

Contents: the speaker registry (names, seats, roles), current parties, the sitting ids and dates (for the status
counter) and the index state (a hash per sitting). No transcript text, no PDFs, no portraits. Re-run and commit after
indexing more sittings, because the public status line and speaker list come from these files.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from tanyadewan.config import load_config

SEED = Path(__file__).resolve().parents[1] / "backend" / "seed"
REGISTRY_KEYS = {"speaker_id", "name", "core_name", "name_variants", "label_variants", "constituencies", "roles"}


def main() -> int:
    cfg = load_config()
    SEED.mkdir(parents=True, exist_ok=True)

    registry = json.loads(cfg.parse.speakers.read_text(encoding="utf-8"))
    extra = {k for person in registry for k in person} - REGISTRY_KEYS
    if extra:
        print(f"speakers.json has unexpected fields {sorted(extra)}: check them before publishing.")
        return 1
    shutil.copy(cfg.parse.speakers, SEED / "speakers.json")

    parties = cfg.parse.speakers.parent / "parties.json"
    if not parties.exists():
        print("parties.json not found: run python -m tanyadewan.speakers.parties first.")
        return 1
    shutil.copy(parties, SEED / "parties.json")

    docs = [json.loads(line) for line in cfg.paths.documents.read_text(encoding="utf-8").splitlines() if line.strip()]
    with (SEED / "documents.jsonl").open("w", encoding="utf-8") as fh:
        for d in docs:
            fh.write(json.dumps({"doc_id": d["doc_id"], "sitting_date": d["sitting_date"]}) + "\n")

    shutil.copy(cfg.index.state, SEED / "index_state.json")

    for f in sorted(SEED.iterdir()):
        print(f"{f.name:20s} {f.stat().st_size / 1024:7.0f} KB")
    print(f"{len(registry)} speakers, {len(docs)} sittings listed -> {SEED}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
