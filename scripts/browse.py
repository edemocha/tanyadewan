"""A local, read-only browser for the parsed Hansard (M1 inspection tool, not the product UI).

    uv run python scripts/browse.py            # http://127.0.0.1:8765

Pages: sittings (with attribution rates), one sitting's turns, the speaker registry, and turns filtered
by resolution method. Serves only data/processed/ from this machine; it listens on 127.0.0.1 only,
because the transcript text is not redistributed. Standard library only.
"""

from __future__ import annotations

import html
import json
import sys
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, quote, urlsplit

from tanyadewan.config import load_config
from tanyadewan.fetch.records import load_records
from tanyadewan.parse.__main__ import RESOLVED

PORT = 8765
PAGE_SIZE = 200

CSS = """
:root{--bg:#fbfaf7;--ink:#1d1d1b;--ink2:#5b5a55;--line:#e6e3dc;--card:#fff;--accent:#0f6e5c;--warn:#b4541e;--bad:#b3261e;
--chip:#f1efe9;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--ink:#ecebe6;--ink2:#a3a19a;--line:#2c2b28;--card:#1c1c1a;
--accent:#5fcfb2;--warn:#f0a36b;--bad:#ff8a80;--chip:#262522;color-scheme:dark}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}
a{color:var(--accent)}header{border-bottom:1px solid var(--line);padding:14px 20px;display:flex;gap:18px;align-items:baseline;flex-wrap:wrap}
header b{font-size:18px}header nav a{margin-right:14px}main{max-width:1180px;margin:0 auto;padding:20px 16px 60px}
h1{font-size:24px;margin:.2em 0 .3em}.sub{color:var(--ink2);margin:0 0 18px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}th{font-size:12px;color:var(--ink2);text-transform:uppercase;letter-spacing:.04em}
.num{text-align:right;font-variant-numeric:tabular-nums}.chip{display:inline-block;padding:1px 8px;border-radius:99px;background:var(--chip);font-size:12px;white-space:nowrap}
.ok{color:var(--accent)}.warn{color:var(--warn)}.bad{color:var(--bad)}.muted{color:var(--ink2)}
.turn{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:8px 0}
.turn.inter{margin-left:36px;border-style:dashed}.who{font-weight:600}.meta{font-size:12px;color:var(--ink2)}
.stage{font-style:italic;color:var(--ink2);font-size:13px}.sec{margin:22px 0 6px;font-size:13px;letter-spacing:.05em;text-transform:uppercase;color:var(--ink2)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin:0 0 20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}.card b{display:block;font-size:22px}
footer{color:var(--ink2);font-size:12px;margin-top:30px}
@media (max-width:640px){td,th{padding:6px}.hide-sm{display:none}}
"""


def esc(v: object) -> str:
    return html.escape("" if v is None else str(v))


def load_turns(doc_id: str) -> list[dict[str, Any]]:
    path = load_config().parse.turns_dir / f"{doc_id}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def report() -> dict[str, Any]:
    path = load_config().parse.report
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"sittings": {}}


def page(title: str, body: str) -> bytes:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} · TanyaDewan</title>
<style>{CSS}</style></head><body><header><b>TanyaDewan</b><span class="muted">parser inspection desk</span>
<nav><a href="/">Sittings</a><a href="/speakers">Speakers</a><a href="/method">By resolution</a></nav></header>
<main>{body}<footer>Transcripts: Penyata Rasmi Dewan Rakyat © Parlimen Malaysia. Local inspection only; nothing here
is published. Each sitting links to its official PDF.</footer></main></body></html>""".encode()


def rate(res: dict[str, int]) -> tuple[int, float]:
    n = sum(res.values())
    ok = sum(v for k, v in res.items() if k in RESOLVED)
    return n, ok / n if n else 0.0


def view_home() -> bytes:
    rep = report()
    docs = load_records(load_config().paths.documents)
    sittings = rep.get("sittings", {})
    total = Counter[str]()
    for s in sittings.values():
        total.update(s["resolution"])
    n, r = rate(dict(total))
    on_disk = sum(1 for d in docs.values() if d.local_path)
    cards = f"""<div class="cards"><div class="card"><b>{len(docs)}</b>sittings listed</div>
<div class="card"><b>{on_disk}</b>PDFs on disk</div><div class="card"><b>{len(sittings)}</b>parsed</div>
<div class="card"><b>{n:,}</b>speaker turns</div><div class="card"><b>{r:.1%}</b>attributed to a speaker</div>
<div class="card"><b>{rep.get("speakers", 0)}</b>people in the registry</div></div>"""
    rows = []
    for d in sorted(docs.values(), key=lambda d: d.sitting_date, reverse=True):
        s = sittings.get(d.doc_id)
        if s:
            tn, tr = rate(s["resolution"])
            cls = "ok" if tr >= 0.97 else "warn" if tr >= 0.9 else "bad"
            parsed = (f'<a href="/sitting/{quote(d.doc_id)}">{tn} turns</a>', f'<span class="{cls}">{tr:.1%}</span>',
                      f"{s['unattributed']}", f"{len(s['debate_pages_without_text']) or ''}")  # fmt: skip
        else:
            parsed = ('<span class="muted">not parsed</span>', "", "", "")
        draft = '<span class="chip warn">draft</span>' if d.is_draft else ""
        rows.append(f"""<tr><td>{esc(d.sitting_date)}</td><td class="hide-sm">P{d.penggal} · M{esc(d.mesyuarat or "Khas")} · Bil. {esc(d.bil)}</td>
<td>{parsed[0]} {draft}</td><td class="num">{parsed[1]}</td><td class="num hide-sm">{parsed[2]}</td>
<td class="num hide-sm">{parsed[3]}</td><td><a href="{esc(d.source_url)}" rel="noopener">official PDF</a></td></tr>""")
    return page(
        "Sittings",
        f"""<h1>Every sitting, read cover to cover</h1>
<p class="sub">So you don't have to. Rows in orange or red have more turns the parser refused to attribute; that's deliberate, not a bug.</p>
{cards}<table><tr><th>Date</th><th class="hide-sm">Meeting</th><th>Turns</th><th class="num">Attributed</th>
<th class="num hide-sm">"Seorang Ahli"</th><th class="num hide-sm">Pages without text</th><th>Source</th></tr>{"".join(rows)}</table>""",
    )


def turn_html(t: dict[str, Any]) -> str:
    ok = t["resolution"] in RESOLVED
    who = esc(t["speaker_raw"])
    badge = f'<span class="chip {"ok" if ok else "bad"}">{esc(t["resolution"])}</span>'
    sid = (
        f' → <a href="/speaker/{quote(str(t["speaker_id"]))}">{esc(t["speaker_id"])}</a>'
        if t["speaker_id"]
        else ""
    )
    stage = (
        f'<div class="stage">[{esc("] [".join(t["stage_directions"]))}]</div>'
        if t["stage_directions"]
        else ""
    )
    q = f" · question {t['question_no'] or t['question_group']}" if t["question_group"] else ""
    return f"""<div class="turn{" inter" if t["is_interjection"] else ""}" id="{esc(t["turn_id"])}">
<div><span class="who">{who}</span>{sid} {badge}</div>
<div class="meta">{esc(t["turn_id"])} · page {esc(t["page_label_start"])} · {esc(t["kind"])} · {esc(t["lang"])}{q}
{" · interjection" if t["is_interjection"] else ""}{" · " + esc(", ".join(t["times"])) if t["times"] else ""}</div>
{stage}<div>{esc(t["text"])}</div></div>"""


def view_sitting(doc_id: str, qs: dict[str, list[str]]) -> bytes:
    turns = load_turns(doc_id)
    docs = load_records(load_config().paths.documents)
    d = docs.get(doc_id)
    if not turns or not d:
        return page("Not found", "<h1>No turns for that sitting</h1><p>Parse it first.</p>")
    start = int((qs.get("from") or ["0"])[0])
    chunk = turns[start : start + PAGE_SIZE]
    parts, section = [], None
    for t in chunk:
        if t["section"] != section:
            section = t["section"]
            parts.append(f'<div class="sec">{esc(section)} · {esc(t["section_heading"] or "")}</div>')
        parts.append(turn_html(t))
    nav = []
    if start > 0:
        nav.append(f'<a href="?from={max(0, start - PAGE_SIZE)}">← earlier</a>')
    if start + PAGE_SIZE < len(turns):
        nav.append(f'<a href="?from={start + PAGE_SIZE}">later →</a>')
    navs = f'<p>{" · ".join(nav)} <span class="muted">turns {start + 1}–{start + len(chunk)} of {len(turns)}</span></p>'
    draft = ' <span class="chip warn">draft: naskhah belum disemak</span>' if d.is_draft else ""
    return page(
        doc_id,
        f"""<h1>{esc(d.sitting_date)} · Bil. {esc(d.bil)}{draft}</h1>
<p class="sub">{esc(d.mesyuarat_title)} · Penggal {d.penggal} · <a href="{esc(d.source_url)}">official PDF</a>.
Dashed boxes are interjections. Red chips are turns left unattributed on purpose.</p>{navs}{"".join(parts)}{navs}""",
    )


def view_speakers() -> bytes:
    path = load_config().parse.speakers
    people = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    rows = []
    for p in sorted(people, key=lambda p: (not p["constituencies"], p["name"])):
        seats = ", ".join(
            f"{c['constituency']} ({c['first_seen'][:7]}–{c['last_seen'][:7]})" for c in p["constituencies"]
        )
        roles = "; ".join(r["role"] for r in p["roles"][-2:])
        rows.append(f"""<tr><td><a href="/speaker/{quote(p["speaker_id"])}">{esc(p["name"])}</a></td><td>{esc(seats) or '<span class="muted">senator / no seat</span>'}</td>
<td class="hide-sm">{esc(roles)}</td><td class="num">{len(p["name_variants"]) + len(p["label_variants"])}</td></tr>""")
    return page(
        "Speakers",
        f"""<h1>The registry</h1><p class="sub">Built only from the attendance lists printed in each sitting.
{len(people)} people. Seats show first and last sitting seen, because seats change hands.</p>
<table><tr><th>Name</th><th>Seat</th><th class="hide-sm">Latest roles</th><th class="num">Spellings</th></tr>{"".join(rows)}</table>""",
    )


def view_speaker(sid: str) -> bytes:
    path = load_config().parse.speakers
    people = (
        {p["speaker_id"]: p for p in json.loads(path.read_text(encoding="utf-8"))} if path.exists() else {}
    )
    p = people.get(sid)
    if not p:
        return page("Not found", "<h1>No such speaker</h1>")
    turns: list[dict[str, Any]] = []
    for f in sorted(load_config().parse.turns_dir.glob("*.jsonl"), reverse=True):
        turns += [t for t in load_turns(f.stem) if t["speaker_id"] == sid and t["text"]]
        if len(turns) >= 60:
            break
    variants = "".join(f"<li>{esc(v)}</li>" for v in p["name_variants"] + p["label_variants"])
    return page(
        p["name"],
        f"""<h1>{esc(p["name"])}</h1><p class="sub">{esc(sid)} · printed as:</p><ul>{variants}</ul>
<div class="sec">Recent turns</div>{"".join(turn_html(t) for t in turns[:60])}""",
    )


def view_method(qs: dict[str, list[str]]) -> bytes:
    method = (qs.get("m") or [""])[0]
    counts: Counter[str] = Counter()
    for s in report().get("sittings", {}).values():
        counts.update(s["resolution"])
    links = " ".join(f'<a class="chip {"ok" if k in RESOLVED else "bad"}" href="?m={quote(k)}">{esc(k)} {v:,}</a>'
                     for k, v in counts.most_common())  # fmt: skip
    body = f'<h1>How each turn was attributed</h1><p class="sub">Pick a method to review it by eye.</p><p>{links}</p>'
    if method:
        found: list[dict[str, Any]] = []
        for f in sorted(load_config().parse.turns_dir.glob("*.jsonl")):
            found += [t for t in load_turns(f.stem) if t["resolution"] == method]
        body += f'<div class="sec">{esc(method)}: first {min(len(found), 100)} of {len(found)}</div>'
        body += "".join(turn_html(t) + f'<div class="meta"><a href="/sitting/{quote(t["doc_id"])}">open sitting</a></div>'
                        for t in found[:100])  # fmt: skip
    return page("By resolution", body)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        url = urlsplit(self.path)
        qs = parse_qs(url.query)
        parts = [p for p in url.path.split("/") if p]
        try:
            if not parts:
                body = view_home()
            elif parts[0] == "sitting" and len(parts) == 2:
                body = view_sitting(parts[1], qs)
            elif parts[0] == "speakers":
                body = view_speakers()
            elif parts[0] == "speaker" and len(parts) == 2:
                body = view_speaker(parts[1])
            elif parts[0] == "method":
                body = view_method(qs)
            else:
                self.send_error(404, "Not here. Even the Hansard has limits.")
                return
        except Exception as e:  # show the error locally rather than a blank page
            body = page("Error", f"<h1>Something tripped</h1><pre>{esc(e)}</pre>")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        pass


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"TanyaDewan inspection desk on http://127.0.0.1:{PORT} (local only). Ctrl+C to leave the gallery.")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
