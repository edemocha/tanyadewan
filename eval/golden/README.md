# Golden set

`questions.jsonl`: one question per line, **written by hand** (CLAUDE.md). Claude may suggest candidates in a
separate file, but never adds them here and never writes reference answers without flagging them for review.

```json
{"id": "q001", "lang": "ms|en|mixed", "type": "factual|speaker|timeline|multi_turn|unanswerable|bait|cross_lingual",
 "question": "...", "filters": {"date_from": null, "date_to": null, "speaker_id": null, "party": null},
 "relevant_turn_ids": ["DR-2025-11-03:0100"], "expected_speakers": ["speaker-id"],
 "reference_answer": "...", "answerable": true}
```

- Turn IDs come from `data/processed/turns/*.jsonl` (the sessions view at `/sidang/<id>#<turn_id>` shows them in the URL).
- Aim for at least 100: about a third each BM, English, mixed; ~10% unanswerable, ~10% bait.
- Only sittings that are indexed can be answered (see `/api/status`).
- If a re-parse shifts turn IDs, remap by (sitting date, speaker, text offset), never regenerate.

Run: `uv run python eval/run_eval.py` → tables in `eval/results/`.
