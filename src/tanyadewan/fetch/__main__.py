"""Crawl both official Hansard sources, merge them, and download sitting PDFs.

    uv run python -m tanyadewan.fetch --parlimen 15 --list-only          # index every sitting, no PDFs
    uv run python -m tanyadewan.fetch --parlimen 15 --sample-per-year 1  # one PDF per year
    uv run python -m tanyadewan.fetch --parlimen 15                      # everything (slow, polite)
    uv run python -m tanyadewan.fetch --parlimen 15 --refresh --recheck-drafts   # look for revised transcripts

Writes data/processed/documents.jsonl (one record per sitting) and PDFs under
data/raw/pdf/ (gitignored, never redistributed).
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from tanyadewan.config import ROOT, load_config
from tanyadewan.fetch import repository, website
from tanyadewan.fetch.client import FetchError, PoliteClient, sha256
from tanyadewan.fetch.cover import read_cover
from tanyadewan.fetch.records import load_records, save_records
from tanyadewan.fetch.sync import (
    combine_sources,
    download,
    merge,
    needs_download,
    pick_sample,
    repair_incomplete,
)

log = logging.getLogger("tanyadewan.fetch")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--parlimen", type=int, default=15)
    ap.add_argument("--source", choices=["both", "repositori", "laman_web"], default="both")
    ap.add_argument("--list-only", action="store_true", help="index sittings without downloading PDFs")
    ap.add_argument("--sample-per-year", type=int, default=0, help="download only N PDFs per calendar year")
    ap.add_argument(
        "--date", action="append", default=[], help="download only these sitting dates (YYYY-MM-DD)"
    )
    ap.add_argument("--limit", type=int, default=0, help="download at most N PDFs")
    ap.add_argument(
        "--refresh", action="store_true", help="re-fetch listing pages instead of using the cache"
    )
    ap.add_argument(
        "--recheck-drafts", action="store_true", help="re-download drafts and keep revised versions"
    )
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    cfg = load_config()
    client = PoliteClient(cfg.fetch, cfg.paths.cache_dir)

    def get(url: str) -> str:
        return client.get_text(url, refresh=args.refresh)

    print(f"Putting on the reading glasses. Crawling Parlimen {args.parlimen}, one request every "
          f"{cfg.fetch.delay_seconds:g}s, like a librarian in slippers.")  # fmt: skip
    listed, unparsed = [], []
    if args.source in ("both", "repositori"):
        root = cfg.fetch.repositori_roots.get(args.parlimen)
        if root:
            print("Source 1: repositori.parlimen.gov.my")
            recs, bad = repository.crawl(get, cfg.fetch.repositori_base_url, args.parlimen, root, print)
            listed += recs
            unparsed += bad
    if args.source in ("both", "laman_web"):
        print("Source 2: www.parlimen.gov.my")
        recs, bad = website.crawl(
            get, cfg.fetch.laman_web_tree_url, args.parlimen, cfg.fetch.laman_web_base_url, print
        )
        listed += recs
        unparsed += bad
        cur_url = cfg.fetch.laman_web_current_url
        recs, bad = website.current_sittings(
            get(cur_url), args.parlimen, cur_url, cfg.fetch.laman_web_base_url
        )
        new_ids = {r.doc_id for r in recs} - {r.doc_id for r in listed}
        if new_ids:
            print(f"  Current meeting (not yet in the archive): {len(new_ids)} sittings")
        listed += [r for r in recs if r.doc_id in new_ids]
        unparsed += bad

    records = merge(load_records(cfg.paths.documents), combine_sources(listed))

    for r in records.values():  # draft flag and Bil. for files downloaded before these were recorded
        if (
            r.local_path
            and (ROOT / r.local_path).exists()
            and (r.is_draft is None or r.sha256 is None or r.text_page_share is None)
        ):
            data = (ROOT / r.local_path).read_bytes()
            cover = read_cover(data)
            r.is_draft, r.sha256, r.bytes = cover.is_draft, sha256(data), len(data)
            r.text_page_share = cover.text_page_share
            r.bil = r.bil if r.bil is not None else cover.bil

    if not args.list_only:
        pool = [r for r in records.values() if r.parlimen == args.parlimen]
        targets = pick_sample(pool, args.sample_per_year) if args.sample_per_year else pool
        if args.date:
            targets = [r for r in pool if r.sitting_date in set(args.date)]
        todo = [r for r in targets if needs_download(r, ROOT) or (args.recheck_drafts and r.is_draft)]
        if args.limit:
            todo = todo[: args.limit]
        counts = {"new": 0, "unchanged": 0, "revised": 0, "failed": 0}
        for r in sorted(todo, key=lambda r: r.sitting_date):
            try:
                status = download(
                    r, client.get_pdf, cfg.paths.pdf_dir, cfg.paths.superseded_dir, ROOT, date.today()
                )
            except FetchError as e:
                log.error("skipped %s: %s", r.doc_id, e)
                counts["failed"] += 1
                continue
            counts[status] += 1
            draft = " (draft: naskhah belum disemak)" if r.is_draft else ""
            print(f"    {status:9} {r.doc_id}  Bil. {r.bil}  {(r.bytes or 0) // 1024} KB{draft}")
        print(f"  Downloads: {counts}")
        broken = [
            r
            for r in pool
            if r.text_page_share is not None and r.text_page_share < cfg.fetch.min_text_page_share
        ]
        for r in broken:  # copies with empty pages: try the other source
            try:
                note = repair_incomplete(r, client.get_pdf, cfg.paths.pdf_dir, cfg.paths.superseded_dir, ROOT,
                                         date.today(), cfg.fetch.min_text_page_share)  # fmt: skip
            except FetchError as e:
                log.error("could not repair %s: %s", r.doc_id, e)
                continue
            print(
                f"    repaired  {r.doc_id}: {note}"
                if note
                else f"    broken    {r.doc_id}: only {r.text_page_share:.0%} of pages have text, no better copy"
            )

    save_records(cfg.paths.documents, records)
    if unparsed:
        report = cfg.paths.documents.with_name("unparsed_listings.tsv")
        report.write_text("\n".join(unparsed) + "\n", encoding="utf-8")
        print(
            f"  {len(unparsed)} listings had unexpected names; see {report.relative_to(ROOT)} (not guessed)."
        )
    rows = [r for r in records.values() if r.parlimen == args.parlimen]
    both = sum(1 for r in rows if r.alternate_urls)
    web_only = sum(1 for r in rows if r.source == "laman_web")
    drafts = sum(1 for r in rows if r.is_draft)
    print(f"Done. {len(rows)} sittings ({both} in both sources, {web_only} website only), "
          f"{sum(1 for r in rows if r.local_path)} PDFs on disk ({drafts} drafts), "
          f"{client.requests_made} requests. One server was asked very nicely. Twice.")  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
