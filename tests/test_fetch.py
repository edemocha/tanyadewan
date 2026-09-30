"""Fetching: both listing formats, file names, merging sources, revisions.

Fixtures are minimal markup shaped like the real listing pages. They contain no Hansard text.
"""

from datetime import date
from pathlib import Path

import pytest

from tanyadewan.fetch import website
from tanyadewan.fetch.records import DocumentRecord, load_records, parse_sitting_filename, save_records
from tanyadewan.fetch.repository import keep_newest, mesyuarat_links, pdf_bitstreams, penggal_links
from tanyadewan.fetch.sync import combine_sources, download, merge, pick_sample

BREADCRUMBS = """
<ul class="breadcrumb"><li><a href="/handle/123456789/1168">KOLEKSI KHAS PARLIMEN MALAYSIA</a></li>
<li><a href="/handle/123456789/1662">2022 - KINI: PARLIMEN KELIMA BELAS</a></li></ul>
"""


def test_repository_listings():
    page = (
        BREADCRUMBS
        + """
    <a href="/handle/123456789/1664">2. PENGGAL KEDUA</a><a href="/handle/123456789/1663">1. PENGGAL PERTAMA</a>"""
    )
    assert [(c.handle, c.number) for c in penggal_links(page)] == [
        ("123456789/1663", 1),
        ("123456789/1664", 2),
    ]
    page = (
        BREADCRUMBS
        + '<a href="/handle/123456789/1736">MESYUARAT&#x20;KETIGA&#x20;(14&#x20;OKTOBER&#x20;2024)</a>'
    )
    assert [(c.number, c.title) for c in mesyuarat_links(page)] == [(3, "MESYUARAT KETIGA (14 OKTOBER 2024)")]
    page = """<a href="/bitstream/1/3432/1/DR1-19122022.pdf">x</a><a href="/bitstream/1/3428/1/DR20-24062024">x</a>
    <a href="/bitstream/1/3428/9/license.txt">x</a>"""
    assert [b.filename for b in pdf_bitstreams(page)] == ["DR1-19122022.pdf", "DR20-24062024"]


WEB_MEETINGS = """<?xml version="1.0" encoding="iso-8859-1"?><tree id='0_15_4'>
<item child='1' id='0_15_4_0' text='Mesyuarat Khas (05/05/2099 - 05/05/2099)'><userdata name='myurl'>#</userdata></item>
<item child='1' id='0_15_4_1' text='Mesyuarat Pertama (03/02/2099 - 06/03/2099)'><userdata name='myurl'>#</userdata></item>
</tree>"""
WEB_SITTINGS = """<?xml version="1.0" encoding="iso-8859-1"?><tree id='0_15_4_1'>
<item child='0' id='a' text='3 Februari 2099'><userdata name='myurl'>javascript:loadResult('/files/hindex/pdf/DR-03022099.pdf','DR-03022099.pdf')</userdata></item>
<item child='0' id='b' text='4 Februari 2099'><userdata name='myurl'>javascript:loadResult('/files/hindex/pdf/DR-04022099 - NOTA - DISEMAK.PM.pdf','x')</userdata></item>
</tree>"""  # fmt: skip


def test_website_tree():
    pages = {
        "T&ajx=1&id=0_15": "<tree id='0_15'><item child='1' id='0_15_4' text='Penggal Keempat'/></tree>",
        "T&ajx=1&id=0_15_4": WEB_MEETINGS,
        "T&ajx=1&id=0_15_4_0": "<tree id='x'/>",
        "T&ajx=1&id=0_15_4_1": WEB_SITTINGS,
    }
    recs, bad = website.crawl(pages.__getitem__, "T", 15, "https://web", lambda s: None)
    assert bad == []
    assert [(r.doc_id, r.penggal, r.mesyuarat, r.bil, r.filename_note) for r in recs] == [
        ("DR-2099-02-03", 4, 1, None, None),
        ("DR-2099-02-04", 4, 1, None, "NOTA - DISEMAK.PM"),
    ]
    assert recs[1].source_url == "https://web/files/hindex/pdf/DR-04022099 - NOTA - DISEMAK.PM.pdf"


def test_website_current_meeting():
    page = """<span class="boxMesyuaratTextA"><strong>Mesyuarat Khas, Penggal Kelima Parlimen Kelima Belas (2099)</strong>
    <a href="javascript:loadResult('/files/hindex/pdf/DR-11082099.pdf','DR-11082099.pdf');">11 Ogos 2099</a>"""
    recs, _ = website.current_sittings(page, 15, "CUR", "https://web")
    assert [(r.doc_id, r.penggal, r.mesyuarat) for r in recs] == [("DR-2099-08-11", 5, None)]
    assert website.current_sittings(page, 14, "CUR", "https://web") == ([], [])  # another Parlimen


@pytest.mark.parametrize("name, bil, day, amended, note", [
    ("DR1-19122022.pdf", 1, date(2022, 12, 19), None, None),
    ("DR20-24062024", 20, date(2024, 6, 24), None, None),
    ("DR-12112024", None, date(2024, 11, 12), None, None),
    ("DR49-09102023.PINDAAN20032025.pdf", 49, date(2023, 10, 9), date(2025, 3, 20), None),
    ("DR-15102025 - BDR APRIL - DISEMAK.PM.pdf", None, date(2025, 10, 15), None, "BDR APRIL - DISEMAK.PM"),
])  # fmt: skip
def test_sitting_filenames(name, bil, day, amended, note):
    p = parse_sitting_filename(name)
    assert p is not None and (p.bil, p.sitting_date, p.amended_on, p.note) == (bil, day, amended, note)


@pytest.mark.parametrize(
    "name", ["DR1-31022023.pdf", "Senarai-Kehadiran.pdf", "DN1-19122022.pdf", "DR1-1912202.pdf"]
)
def test_unexpected_names_are_not_guessed(name):
    assert parse_sitting_filename(name) is None


def rec(
    url: str, source: str = "repositori", amended: str | None = None, day: str = "2099-10-09"
) -> DocumentRecord:
    return DocumentRecord(doc_id=f"DR-{day}", sitting_date=day, parlimen=15, penggal=2, mesyuarat=3,
                          mesyuarat_title="", bil=49, source=source, source_url=url, listing_url="",
                          filename=url.rsplit("/", 1)[-1], amended_on=amended)  # fmt: skip


@pytest.mark.parametrize("order", [0, 1])
def test_amended_transcript_replaces_original(order):
    pair = [
        rec("https://r/DR49-09102099.pdf"),
        rec("https://r/DR49-09102099.PINDAAN20032100.pdf", amended="2100-03-20"),
    ]
    records: dict[str, DocumentRecord] = {}
    for r in pair if order == 0 else pair[::-1]:
        keep_newest(records, r)
    kept = records["DR-2099-10-09"]
    assert kept.source_url.endswith("PINDAAN20032100.pdf") and kept.superseded_urls == [
        "https://r/DR49-09102099.pdf"
    ]


def test_repository_preferred_website_kept_as_alternate():
    out = combine_sources(
        [rec("https://web/DR-09102099.pdf", "laman_web"), rec("https://r/DR49-09102099.pdf")]
    )
    r = out["DR-2099-10-09"]
    assert (r.source, r.alternate_urls) == ("repositori", ["https://web/DR-09102099.pdf"])


def test_merge_keeps_download_info_and_detects_new_versions():
    old = rec("https://r/a.pdf")
    old.sha256, old.local_path, old.fetch_date, old.is_draft = "abc", "data/raw/pdf/x.pdf", "2099-01-01", True
    same = merge({old.doc_id: old}, {old.doc_id: rec("https://r/a.pdf")})[old.doc_id]
    assert (same.sha256, same.fetch_date, same.is_draft) == ("abc", "2099-01-01", True)
    newer = merge({old.doc_id: old}, {old.doc_id: rec("https://r/b.pdf")})[old.doc_id]
    assert newer.fetch_date is None and newer.superseded_urls == ["https://r/a.pdf"]  # will be downloaded


def test_revised_download_keeps_old_version(tmp_path: Path, monkeypatch):  # type: ignore[no-untyped-def]
    from tanyadewan.fetch import sync
    from tanyadewan.fetch.cover import Cover

    monkeypatch.setattr(sync, "read_cover", lambda data: Cover(49, data.endswith(b"draft"), 1.0))
    r = rec("https://r/a.pdf")
    pdf_dir, old_dir = tmp_path / "pdf", tmp_path / "superseded"
    assert download(r, lambda u: b"%PDF v1 draft", pdf_dir, old_dir, tmp_path, date(2099, 1, 1)) == "new"
    assert r.is_draft is True
    assert (
        download(r, lambda u: b"%PDF v1 draft", pdf_dir, old_dir, tmp_path, date(2099, 1, 2)) == "unchanged"
    )
    assert download(r, lambda u: b"%PDF v2 final", pdf_dir, old_dir, tmp_path, date(2099, 1, 3)) == "revised"
    assert r.is_draft is False and len(r.previous_sha256) == 1
    assert (
        len(list(old_dir.glob("*.pdf"))) == 1
        and (tmp_path / str(r.local_path)).read_bytes() == b"%PDF v2 final"
    )


def test_records_round_trip(tmp_path: Path):
    path = tmp_path / "documents.jsonl"
    r = rec("https://r/a.pdf")
    r.alternate_urls = ["https://web/a.pdf"]
    save_records(path, {r.doc_id: r})
    assert load_records(path)[r.doc_id] == r


def test_sample_spreads_across_each_year():
    rows = [rec(f"u{m}", day=f"2099-{m:02d}-01") for m in range(1, 11)] + [rec("v", day="2100-03-01")]
    assert [r.sitting_date for r in pick_sample(rows, 2)] == ["2099-01-01", "2099-06-01", "2100-03-01"]


def test_broken_copy_is_replaced_by_the_other_source(tmp_path: Path, monkeypatch):  # type: ignore[no-untyped-def]
    from tanyadewan.fetch import sync
    from tanyadewan.fetch.cover import Cover
    from tanyadewan.fetch.sync import repair_incomplete

    monkeypatch.setattr(sync, "read_cover", lambda data: Cover(11, False, 0.02 if b"empty" in data else 0.98))
    r = rec("https://repositori.parlimen.gov.my/a.pdf")
    r.alternate_urls = ["https://www.parlimen.gov.my/files/a.pdf"]
    pdfs = {r.source_url: b"%PDF empty pages", r.alternate_urls[0]: b"%PDF full text"}
    download(r, pdfs.__getitem__, tmp_path / "pdf", tmp_path / "old", tmp_path, date(2099, 1, 1))
    assert r.text_page_share == 0.02
    note = repair_incomplete(
        r, pdfs.__getitem__, tmp_path / "pdf", tmp_path / "old", tmp_path, date(2099, 1, 2), 0.9
    )
    assert note and (r.source, r.source_url) == ("laman_web", "https://www.parlimen.gov.my/files/a.pdf")
    assert r.alternate_urls == ["https://repositori.parlimen.gov.my/a.pdf"] and r.text_page_share == 0.98
    assert (tmp_path / str(r.local_path)).read_bytes() == b"%PDF full text"
    # a later crawl lists the repository copy first again: the switch must stick
    relisted = combine_sources([rec("https://repositori.parlimen.gov.my/a.pdf"),
                                rec("https://www.parlimen.gov.my/files/a.pdf", "laman_web")])  # fmt: skip
    kept = merge({r.doc_id: r}, relisted)[r.doc_id]
    assert kept.source_url == "https://www.parlimen.gov.my/files/a.pdf" and kept.fetch_date is not None
