"""Party affiliation from each member's official Parlimen profile page (the "Parti" row).

The profile shows the CURRENT party only. So each entry is a dated snapshot ({party, as_of, source}), stored
per person as a list so later snapshots (or sitting-dated data) can be appended, never overwritten. Party is
a filter label only: no scoring, no rankings. parties.json is gitignored like the rest of data/processed/.

    uv run python -m tanyadewan.speakers.parties            # fetch missing profiles (4 s apart), write parties.json
    uv run python -m tanyadewan.speakers.parties --refresh  # add a new snapshot for everyone
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import date
from functools import lru_cache
from html.parser import HTMLParser
from typing import Any

from tanyadewan.config import load_config
from tanyadewan.fetch.client import FetchError, PoliteClient

log = logging.getLogger("tanyadewan.parties")


class _ProfileParty(HTMLParser):
    """<tr><td><strong>Parti</strong></td><td>BN</td></tr>"""

    def __init__(self) -> None:
        super().__init__()
        self.party: str | None = None
        self._in_label = False
        self._want_value = False
        self._in_td = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "td":
            self._in_td = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "td":
            self._in_td = False
            if self._in_label:
                self._in_label, self._want_value = False, True

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text or not self._in_td:
            return
        if self._want_value and self.party is None:
            self.party = re.sub(r"\s+", " ", text)
            self._want_value = False
        elif text.lower() == "parti":
            self._in_label = True


def parse_party(html: str) -> str | None:
    p = _ProfileParty()
    p.feed(html)
    return p.party


def party_on(history: list[dict[str, Any]], day: str) -> str | None:
    """Party for a sitting date (YYYY-MM-DD): the latest snapshot; snapshots carry no start date."""
    return history[-1]["party"] if history else None


@lru_cache(maxsize=1)
def current_parties() -> dict[str, str]:
    """speaker_id -> latest snapshot party; empty when parties.json doesn't exist."""
    path = load_config().parse.speakers.parent / "parties.json"
    data: dict[str, list[dict[str, str]]] = (
        json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    )
    return {sid: h[-1]["party"] for sid, h in data.items() if h}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cfg = load_config()
    photos: dict[str, Any] = json.loads(cfg.photos.file.read_text(encoding="utf-8"))
    out_path = cfg.parse.speakers.parent / "parties.json"
    parties: dict[str, list[dict[str, str]]] = (
        json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    )
    client = PoliteClient(cfg.fetch, cfg.paths.cache_dir)
    today = date.today().isoformat()
    missing = 0
    for i, (sid, info) in enumerate(sorted(photos.items()), 1):
        if sid in parties and not args.refresh:
            continue
        url = info["profile_url"]
        try:
            party = parse_party(client.get_text(url, refresh=args.refresh))
        except FetchError as e:
            log.warning("%s: %s", sid, e)
            continue
        if not party:
            missing += 1
            log.warning("%s: no Parti row on %s", sid, url)
            continue
        parties.setdefault(sid, []).append({"party": party, "as_of": today, "source": url})
        out_path.write_text(json.dumps(parties, ensure_ascii=False, indent=1), encoding="utf-8")
        log.info("[%d/%d] %s -> %s", i, len(photos), sid, party)
    log.info("done: %d with party, %d without", len(parties), missing)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
