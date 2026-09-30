"""Photo matching: a face is attached only when seat AND name agree. Placeholder names only."""

from __future__ import annotations

from typing import Any

import pymupdf

from tanyadewan.config import load_config
from tanyadewan.speakers.photos import Member, match, parse_members, thumbnail

BASE = "https://example.test"

LIST_HTML = """
<ul>
 <li><div>
  <a href="profile-ahli.html?uweb=dr&id=1">
   <img alt="Photo" src="/images/webuser/ahli/2022/P901.jpg" class="picture">
   <div class="full-name"><span class="honorific"><abbr></abbr></span>
    <span class="first-name">YB Dato' Sri MP_A bin LOREM</span></div>
  </a>
  <div class="caucus">X</div> <div class="constituency">P901</div> <div class="province">Seat-One Baharu</div>
 </div></li>
 <li><div>
  <a href="profile-ahli.html?uweb=dr&id=2">
   <img alt="Photo" src="/images/webuser/ahli/2022/P902.jpg" class="picture">
   <div class="full-name"><span class="first-name">YB Tuan MP_B IPSUM</span></div>
  </a>
  <div class="constituency">P902</div> <div class="province">Seat Two</div>
 </div></li>
</ul>
"""


def person(sid: str, core: str, *seats: str) -> dict[str, Any]:
    return {"speaker_id": sid, "core_name": core,
            "constituencies": [{"constituency": s, "first_seen": "2023-01-01", "last_seen": "2024-01-01"} for s in seats]}  # fmt: skip


def member(name: str, seat: str) -> Member:
    return Member(
        name=name, seat_code="P900", constituency=seat, photo_url=f"{BASE}/p.jpg", profile_url=f"{BASE}/x"
    )


def test_parse_member_list() -> None:
    members = parse_members(LIST_HTML, BASE)
    assert [m.seat_code for m in members] == ["P901", "P902"]
    assert members[0].name == "YB Dato' Sri MP_A bin LOREM"
    assert members[0].constituency == "Seat-One Baharu"
    assert members[0].photo_url == f"{BASE}/images/webuser/ahli/2022/P901.jpg"
    assert members[0].profile_url == f"{BASE}/profile-ahli.html?uweb=dr&id=1"


def test_seat_and_name_must_both_match() -> None:
    people = [person("mp-a", "mp_a lorem", "Seat One")]
    assert "mp-a" in match([member("YB Tuan MP_A bin LOREM", "Seat One")], people)[0]
    # same seat, different person (a by-election winner): no photo rather than the wrong face
    photos, review = match([member("YB Tuan MP_Z DOLOR", "Seat One")], people)
    assert photos == {} and len(review) == 1
    # same name, seat never held
    assert match([member("YB Tuan MP_A bin LOREM", "Seat Nine")], people)[0] == {}


def test_seat_spellings_count_one_person() -> None:
    people = [person("mp-a", "mp_a lorem", "Seat-One Baharu", "Seat One Baharu")]
    assert "mp-a" in match([member("YB MP_A LOREM", "Seat One Baharu")], people)[0]


def test_short_registry_name_matches_only_one_way() -> None:
    short = [person("mp-a", "mp_a", "Seat One")]
    assert "mp-a" in match([member("YB Dato' MP_A binti LOREM", "Seat One")], short)[0]
    # a corrupt registry "name" that happens to contain the member's words must not claim the photo
    corrupt = [person("junk", "1 menteri mp_x lorem 2 menteri mp_a lorem 3 menteri", "Seat One")]
    assert match([member("YB MP_A LOREM", "Seat One")], corrupt)[0] == {}


def test_thumbnail_is_small_jpeg() -> None:
    cfg = load_config().photos
    big = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 1200, 1600), False)
    big.clear_with(200)
    small = pymupdf.Pixmap(thumbnail(big.tobytes("png"), cfg))
    assert small.width < 2 * cfg.thumb_px and small.height < 2 * cfg.thumb_px
    assert thumbnail(big.tobytes("png"), cfg)[:2] == b"\xff\xd8"
