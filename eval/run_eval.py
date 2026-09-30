"""Retrieval evaluation over the hand-written golden set (CLAUDE.md, M3).

    uv run python eval/run_eval.py                                   # every config in eval/configs/
    uv run python eval/run_eval.py --config eval/configs/hybrid_rerank.yaml

Each config names a retrieval setup (mode, rerank, translate_query, top_k). For every golden question the
harness runs retrieval only (no answer generation, so no LLM cost except query translation) and scores:

  recall@k      share of the labelled relevant turns found in the top k
  MRR           1 / rank of the first relevant turn
  nDCG@k        rank-aware gain, binary relevance
  refusal       on answerable=false questions: did retrieval say "not found"? (correct refusal rate)
  false refusal on answerable questions: did it wrongly say "not found"?
  latency       p50 / p95 of the whole retrieval call

All broken down by the question's language (ms / en / mixed). Results are written as a markdown table to
eval/results/<date>-<config>.md and a JSON line per question to eval/results/<date>-<config>.jsonl, so
changes can be compared and committed. The golden set is written by hand (CLAUDE.md); this script never
writes to it.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from tanyadewan.retrieve.search import Filters, search
from tanyadewan.speakers.parties import current_parties

EVAL = Path(__file__).resolve().parent
GOLDEN = EVAL / "golden" / "questions.jsonl"
CONFIGS = EVAL / "configs"
RESULTS = EVAL / "results"


@dataclass(frozen=True)
class Experiment:
    name: str
    mode: str
    rerank: bool
    translate: bool
    k: int
    note: str


def load_experiment(path: Path) -> Experiment:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Experiment(path.stem, str(raw["mode"]), bool(raw["rerank"]), bool(raw.get("translate_query", False)),
                      int(raw.get("top_k", 8)), str(raw.get("note", "")))  # fmt: skip


def load_golden(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def ndcg(ranked: list[str], relevant: set[str], k: int) -> float:
    dcg = sum(1 / math.log2(i + 2) for i, t in enumerate(ranked[:k]) if t in relevant)
    ideal = sum(1 / math.log2(i + 2) for i in range(min(len(relevant), k)))
    return dcg / ideal if ideal else 0.0


def score_question(q: dict[str, Any], exp: Experiment) -> dict[str, Any]:
    f = q.get("filters") or {}
    members = tuple(sid for sid, p in current_parties().items() if p == f["party"]) if f.get("party") else ()
    result = search(q["question"], Filters(f.get("date_from"), f.get("date_to"), f.get("speaker_id"), speaker_ids=members),
                    exp.k, mode=exp.mode, rerank=exp.rerank, translate=exp.translate)  # fmt: skip
    ranked: list[str] = []
    for h in result.hits:  # sub-chunks of one turn count once, at their best rank
        tid = str(h.payload.get("turn_id"))
        if tid not in ranked:
            ranked.append(tid)
    relevant = set(q.get("relevant_turn_ids") or [])
    first = next((i + 1 for i, t in enumerate(ranked) if t in relevant), None)
    return {
        "id": q["id"], "lang": q.get("lang", "?"), "type": q.get("type", "?"), "answerable": q.get("answerable", True),
        "not_found": result.not_found, "best_relevance": result.best_relevance, "ms": result.ms.get("total", 0),
        "recall": (len(relevant & set(ranked)) / len(relevant)) if relevant else None,
        "mrr": (1 / first) if first else 0.0, "ndcg": ndcg(ranked, relevant, exp.k) if relevant else None,
        "ranked": ranked, "queries": result.queries,
    }  # fmt: skip


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ans = [r for r in rows if r["answerable"] and r["recall"] is not None]
    unans = [r for r in rows if not r["answerable"]]
    ms = sorted(r["ms"] for r in rows)

    def mean(xs: list[float]) -> float | None:
        return statistics.mean(xs) if xs else None

    return {
        "n": len(rows),
        "recall": mean([r["recall"] for r in ans]), "mrr": mean([r["mrr"] for r in ans]),
        "ndcg": mean([r["ndcg"] for r in ans]),
        "refusal": mean([1.0 if r["not_found"] else 0.0 for r in unans]),
        "false_refusal": mean([1.0 if r["not_found"] else 0.0 for r in rows if r["answerable"]]),
        "p50_ms": ms[len(ms) // 2] if ms else None, "p95_ms": ms[min(len(ms) - 1, int(len(ms) * 0.95))] if ms else None,
    }  # fmt: skip


def fmt(v: Any) -> str:
    return "–" if v is None else (f"{v:.3f}" if isinstance(v, float) else str(v))


def table(exp: Experiment, rows: list[dict[str, Any]]) -> str:
    head = f"| slice | n | recall@{exp.k} | MRR | nDCG@{exp.k} | refusal | false refusal | p50 ms | p95 ms |"
    lines = [f"## {exp.name}", "", exp.note, "", head, "|" + "---|" * 9]
    for label, part in [("all", rows)] + [
        (lang, [r for r in rows if r["lang"] == lang]) for lang in ("ms", "en", "mixed")
    ]:
        if part:
            s = summarise(part)
            lines.append(f"| {label} | {s['n']} | {fmt(s['recall'])} | {fmt(s['mrr'])} | {fmt(s['ndcg'])} | "
                         f"{fmt(s['refusal'])} | {fmt(s['false_refusal'])} | {fmt(s['p50_ms'])} | {fmt(s['p95_ms'])} |")  # fmt: skip
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--config", type=Path, action="append", help="one experiment YAML (repeatable); default: all"
    )
    ap.add_argument("--golden", type=Path, default=GOLDEN)
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not args.golden.exists() or not load_golden(args.golden):
        print(
            f"No golden questions yet at {args.golden}. The golden set is hand-written (see eval/golden/README.md)."
        )
        return 1
    golden = load_golden(args.golden)
    RESULTS.mkdir(exist_ok=True)
    for path in args.config or sorted(CONFIGS.glob("*.yaml")):
        exp = load_experiment(path)
        print(f"{exp.name}: {len(golden)} questions…")
        rows = [score_question(q, exp) for q in golden]
        stem = RESULTS / f"{date.today().isoformat()}-{exp.name}"
        stem.with_suffix(".jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
        )
        md = table(exp, rows)
        stem.with_suffix(".md").write_text(md, encoding="utf-8")
        print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
