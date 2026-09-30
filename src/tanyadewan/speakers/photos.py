"""Official portrait for each registry speaker, from Parlimen's member list (ahli-dewan.html).

The list shows the CURRENT member of each seat with a photo named by seat code (P001.jpg ...). A seat can
change hands (by-elections), so a seat match alone could put the wrong face next to a quote, which is the
same failure as misattribution. A photo is attached only when BOTH hold:
  - the registry speaker sat for that seat at some point in the indexed sittings, and
  - their core name matches the name printed on the list (exact, short form, or near-identical spelling, among that seat's holders).
Anything else gets no photo (the UI falls back to initials) and is listed for review.

The originals are ~1.7 MB each, far too heavy to hotlink for a 36px avatar. Each matched photo is downloaded
once (politely, via PoliteClient) and kept only as a small thumbnail in data/processed/photos/ (gitignored,
never committed; same rule as the PDFs). The UI links every avatar back to the official profile page.

    uv run python -m tanyadewan.speakers.photos            # match + build missing thumbnails
    uv run python -m tanyadewan.speakers.photos --refresh  # re-fetch the member list page first
    uv run python -m tanyadewan.speakers.photos --no-thumbs
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import pymupdf

from tanyadewan.config import PhotosConfig, load_config
from tanyadewan.fetch.client import PoliteClient
from tanyadewan.speakers.names import core_name
from tanyadewan.speakers.registry import FUZZY_RATIO, _seat

log = logging.getLogger("tanyadewan.photos")


@dataclass(frozen=True)
class Member:
    name: str  # as printed on the list, titles included
    seat_code: str  # "P001"
    constituency: str
    photo_url: str
    profile_url: str


class _MemberList(HTMLParser):
    """Each member is an <li> holding: <a href=profile><img class=picture src=photo> <span class=first-name>
    name</span></a> ... <div class=constituency>P001</div> <div class=province>Seat name</div>."""

    FIELDS = {"first-name": "name", "constituency": "seat_code", "province": "constituency"}

    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base = base_url
        self.members: list[Member] = []
        self._cur: dict[str, str] = {}
        self._field: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v or "" for k, v in attrs}
        classes = set(a.get("class", "").split())
        if tag == "li":
            self._cur = {}
        elif tag == "a" and "profile-ahli" in a.get("href", ""):
            self._cur["profile_url"] = urljoin(self.base + "/", a["href"])
        elif tag == "img" and "picture" in classes:
            self._cur["photo_url"] = urljoin(self.base + "/", a.get("src", ""))
        for cls, key in self.FIELDS.items():
            if cls in classes:
                self._field = key

    def handle_data(self, data: str) -> None:
        if self._field and data.strip():
            self._cur[self._field] = (self._cur.get(self._field, "") + " " + data.strip()).strip()

    def handle_endtag(self, tag: str) -> None:
        if tag in ("span", "div"):
            self._field = None
        elif (
            tag == "li"
            and {"name", "seat_code", "constituency", "photo_url", "profile_url"} <= self._cur.keys()
        ):
            self.members.append(Member(**{k: self._cur[k] for k in Member.__dataclass_fields__}))
            self._cur = {}


def parse_members(html: str, base_url: str) -> list[Member]:
    p = _MemberList(base_url)
    p.feed(html)
    return p.members


def _short_form_of(registry_core: str, site_core: str) -> bool:
    """Every word of the registry's name appears in the site's fuller name ("nancy" / "nancy shukri")."""
    words = set(registry_core.split())
    return bool(words) and words <= set(site_core.split())


def _same_spelling(a: str, b: str) -> bool:
    """Near-identical spelling ("Yassin" / "Yasin"): the registry's fuzzy ratio, without its two-way containment."""
    return SequenceMatcher(None, a, b).ratio() >= FUZZY_RATIO


def match(members: list[Member], people: list[dict[str, Any]]) -> tuple[dict[str, dict[str, str]], list[str]]:
    """speaker_id -> photo record, plus a review list of members that matched no one (or more than one)."""
    by_seat: dict[str, list[dict[str, Any]]] = {}
    for person in people:
        for c in person["constituencies"]:
            by_seat.setdefault(_seat(c["constituency"]), []).append(person)
    photos: dict[str, dict[str, str]] = {}
    review: list[str] = []
    for m in members:
        core = core_name(m.name)
        # one person can sit under two spellings of the same seat ("Kulim-Bandar Baharu"): count people, not rows
        holders = list({p["speaker_id"]: p for p in by_seat.get(_seat(m.constituency), [])}.values())
        # the seat already narrows it to its holders, so a short printed name is enough ("Nancy" within
        # "Nancy Shukri"); only in that direction, so a corrupt registry "name" can't swallow a real one
        hits = [p for p in holders if p["core_name"] == core] or [
            p for p in holders if _short_form_of(p["core_name"], core) or _same_spelling(p["core_name"], core)
        ]
        if len(hits) != 1:
            review.append(f"{m.seat_code} {m.constituency}: {m.name!r} -> {len(hits)} registry matches")
            continue
        photos[hits[0]["speaker_id"]] = {**asdict(m), "matched_on": "seat+name"}
    return photos, review


def thumbnail(image: bytes, cfg: PhotosConfig) -> bytes:
    """Shrink by halves until the longest side is at most ~2x the target, then let the viewer's scaling
    do the rest; PyMuPDF (already a dependency) does this without Pillow."""
    pix = pymupdf.Pixmap(image)  # type: ignore[no-untyped-call]
    if pix.alpha:
        pix = pymupdf.Pixmap(pix, 0)  # type: ignore[no-untyped-call]
    while max(pix.width, pix.height) >= 2 * cfg.thumb_px:
        pix.shrink(1)  # type: ignore[no-untyped-call]
    out: bytes = pix.tobytes("jpg", jpg_quality=cfg.jpeg_quality)  # type: ignore[no-untyped-call]
    return out


def build_thumbnails(photos: dict[str, dict[str, str]], client: PoliteClient, cfg: PhotosConfig) -> int:
    cfg.thumb_dir.mkdir(parents=True, exist_ok=True)
    made = 0
    for sid, rec in photos.items():
        out = cfg.thumb_dir / f"{sid}.jpg"
        if out.exists():
            continue
        try:
            out.write_bytes(thumbnail(client.get_image(rec["photo_url"]), cfg))
            made += 1
        except Exception as e:  # one bad photo shouldn't stop the rest; that speaker shows initials
            log.warning("  no thumbnail for %s: %s", sid, e)
    return made


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true", help="re-fetch the member list page")
    ap.add_argument("--no-thumbs", action="store_true", help="match only; don't download photos")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cfg = load_config()
    client = PoliteClient(cfg.fetch, cfg.paths.cache_dir)
    html = client.get_text(cfg.fetch.laman_web_members_url, refresh=args.refresh)
    members = parse_members(html, cfg.fetch.laman_web_base_url)
    people = json.loads(cfg.parse.speakers.read_text(encoding="utf-8"))
    photos, review = match(members, people)
    out: Path = cfg.photos.file
    out.write_text(json.dumps(photos, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("Member list: %d members. Photos matched: %d. For review: %d. -> %s",
             len(members), len(photos), len(review), out)  # fmt: skip
    for line in review:
        log.info("  review: %s", line)
    if not args.no_thumbs:
        todo = sum(not (cfg.photos.thumb_dir / f"{sid}.jpg").exists() for sid in photos)
        log.info(
            "Building %d thumbnails (one polite request each, %.0fs apart)...", todo, cfg.fetch.delay_seconds
        )
        log.info(
            "Thumbnails built: %d -> %s", build_thumbnails(photos, client, cfg.photos), cfg.photos.thumb_dir
        )


if __name__ == "__main__":
    main()
