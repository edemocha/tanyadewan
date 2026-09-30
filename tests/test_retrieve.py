"""Retrieval pieces that run without Qdrant, Ollama or an LLM. Placeholder text only (CLAUDE.md)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from tanyadewan.generate.prompt import build_messages, question_language
from tanyadewan.index.sparse import BM25, term_index, tokens
from tanyadewan.retrieve.translate import to_malay

BM = BM25(k1=1.2, b=0.75, avg_len=10)


def test_tokens_split_and_keep_digits() -> None:
    assert tokens("LOREM-ipsum, RM64.1 bil. 3 a") == ["lorem", "ipsum", "rm64", "1", "bil", "3"]


def test_term_index_is_stable_and_31_bit() -> None:
    assert term_index("lorem") == term_index("lorem")
    assert 0 <= term_index("ipsum") < 2**31


def weights(text: str) -> dict[int, float]:
    v = BM.document(text)
    return dict(zip(v.indices, v.values, strict=True))


def test_bm25_document_saturates_and_normalises_length() -> None:
    many = weights("lorem " * 20)
    assert len(many) == 1
    assert next(iter(many.values())) < 1.2 + 1  # tf saturation: never above k1 + 1
    # the same single occurrence weighs more in a short chunk than in a long one
    assert (
        weights("lorem ipsum")[term_index("lorem")] > weights("lorem " + "dolor " * 40)[term_index("lorem")]
    )


def test_bm25_query_is_one_per_distinct_term() -> None:
    q = BM.query("lorem lorem ipsum")
    assert sorted(q.indices) == sorted({term_index("lorem"), term_index("ipsum")})
    assert set(q.values) == {1.0}
    assert BM.query("?!").indices == []


def test_question_language() -> None:
    assert question_language("Apa yang MP_A cakap pasal LOREM?") == "ms"
    assert question_language("What did MP_A say about LOREM?") == "en"
    assert question_language("LOREM") == "ms"


def test_answer_language_instruction_is_in_prompt() -> None:
    user = build_messages("What did MP_A say about LOREM?", [], 100)[1]["content"]
    assert user.endswith("Write the whole answer in English.")


def test_malay_questions_are_not_translated() -> None:
    assert to_malay("Apa yang MP_A cakap pasal LOREM?") is None  # no LLM call for a BM question


def _run_eval() -> ModuleType:  # eval/ is a script folder, not a package
    spec = importlib.util.spec_from_file_location(
        "run_eval", Path(__file__).parents[1] / "eval" / "run_eval.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["run_eval"] = mod  # its dataclasses look their module up by name
    spec.loader.exec_module(mod)
    return mod


def test_ndcg() -> None:
    ev = _run_eval()
    assert ev.ndcg(["a", "b"], {"a"}, 8) == 1.0
    assert abs(ev.ndcg(["x", "a"], {"a"}, 8) - 1 / 1.5849625) < 1e-6  # 1/log2(3)
    assert ev.ndcg(["x"], {"a"}, 8) == 0.0


def test_config_override_merges_nested_keys() -> None:
    from tanyadewan.config import _merge

    merged = _merge({"a": {"x": 1, "y": 2}, "b": 1}, {"a": {"y": 3}, "c": 4})
    assert merged == {"a": {"x": 1, "y": 3}, "b": 1, "c": 4}


def test_public_limits_per_ip_and_per_day(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi import HTTPException, Request

    from tanyadewan.api import main

    def req(ip: str) -> Request:
        return Request({"type": "http", "headers": [(b"x-forwarded-for", ip.encode())]})

    main._hits.clear()
    monkeypatch.setattr(main, "PUBLIC", False)
    for _ in range(main._RATE + 3):
        main._limit(req("9.9.9.9"))  # local use is never limited
    main._hits.clear()
    monkeypatch.setattr(main, "PUBLIC", True)
    main._day.update(date="", n=0)
    for _ in range(main._RATE):
        main._limit(req("1.1.1.1"))
    with pytest.raises(HTTPException) as e:
        main._limit(req("1.1.1.1"))
    assert e.value.status_code == 429
    main._limit(req("2.2.2.2"))  # another visitor is unaffected
    main._hits.clear()
    main._day.update(n=main._CAP)
    with pytest.raises(HTTPException):
        main._limit(req("3.3.3.3"))
    main._day.update(date="", n=0)


def test_parse_party_reads_profile_row_and_filter_uses_any_of_members() -> None:
    from qdrant_client import models

    from tanyadewan.retrieve.search import Filters, _qdrant_filter
    from tanyadewan.speakers.parties import parse_party

    html = "<table><tr><td><strong>Jawatan</strong></td><td>X</td></tr><tr><td><strong>Parti</strong></td><td> BN </td></tr></table>"
    assert parse_party(html) == "BN"
    assert parse_party("<table><tr><td>Tiada</td></tr></table>") is None
    flt = _qdrant_filter(Filters(speaker_ids=("a", "b")))
    assert flt is not None and isinstance(flt.must[0].match, models.MatchAny)  # type: ignore[union-attr,index]


def test_reranker_never_runs_the_session_concurrently() -> None:
    import threading
    import time

    import numpy as np
    from tokenizers import Tokenizer, models, pre_tokenizers

    from tanyadewan.retrieve.rerank import Reranker

    class FakeSession:
        def __init__(self) -> None:
            self.active = 0
            self.peak = 0

        def run(self, *_: object) -> list[np.ndarray]:
            self.active += 1
            self.peak = max(self.peak, self.active)
            time.sleep(0.02)
            self.active -= 1
            return [np.zeros((1, 1), dtype=np.float32)]

    tok = Tokenizer(models.WordLevel({"<pad>": 0, "a": 1, "[UNK]": 2}, unk_token="[UNK]"))
    tok.pre_tokenizer = pre_tokenizers.Whitespace()
    tok.enable_padding(pad_id=0, pad_token="<pad>")
    rr = object.__new__(Reranker)
    rr.session = FakeSession()  # type: ignore[assignment]
    rr.tokenizer = tok
    rr._run_lock = threading.Lock()
    rr.cfg = type("C", (), {"batch_size": 1})()  # type: ignore[assignment]
    threads = [threading.Thread(target=rr.scores, args=("a", ["a", "a"])) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert rr.session.peak == 1  # type: ignore[attr-defined]


def test_get_reranker_builds_the_model_once_under_concurrent_first_requests(monkeypatch: object) -> None:
    import threading
    import time

    from tanyadewan.retrieve import rerank

    built: list[int] = []

    class Slow:
        def __init__(self, cfg: object) -> None:
            built.append(1)
            time.sleep(0.05)

    rerank._build.cache_clear()
    monkeypatch.setattr(rerank, "Reranker", Slow)  # type: ignore[attr-defined]
    cfg = object()
    threads = [threading.Thread(target=rerank.get_reranker, args=(cfg,)) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    rerank._build.cache_clear()
    assert len(built) == 1


def test_highlight_terms_keep_topic_words_from_both_query_versions() -> None:
    from tanyadewan.generate.answer import highlight_terms

    terms = highlight_terms(["Apa yang MP cakap pasal PTPTN?", "What did MPs say about PTPTN loan repayment?"])
    assert "ptptn" in terms and "loan" in terms and "repayment" in terms
    assert terms.count("ptptn") == 1  # no duplicates across the two versions
    assert not {"apa", "yang", "mp", "cakap", "pasal", "what", "did", "say", "about"} & set(terms)


def test_junk_speaker_names_are_not_offered_in_the_filter() -> None:
    from tanyadewan.api.main import _is_junk_name

    assert _is_junk_name({"core_name": "lorem 2023", "name": "LOREM 2023"})  # digits: a date, not a person
    assert _is_junk_name({"core_name": "lorem ipsum", "name": "Lorem \ufffdipsum"})  # broken encoding
    assert _is_junk_name({"core_name": "lorem " * 30, "name": "x"})  # a list glued into one name
    assert not _is_junk_name({"core_name": "lorem ipsum", "name": "Dato' Lorem Ipsum"})


def test_attendance_date_header_is_not_an_entry_number() -> None:
    from tanyadewan.parse.attendance import split_numbered

    # Real entries from the first sitting's list, which is printed under "19 DISEMBER 2022 (ISNIN)": the "19"
    # used to be read as entry 19, which swallowed entries 1-19 into one junk name.
    text = (
        "19 DISEMBER 2022 (ISNIN) 1 Perdana Menteri Dan Menteri Kewangan, Dato' Seri Anwar Bin Ibrahim (Tambun) "
        "2 Timbalan Menteri Ekonomi, Dato Hajah Hanifah Hajar Taib (Mukah) "
        "3 Timbalan Menteri Kerja Raya, Dato' Sri Haji Abdul Rahman Bin Mohamad"
    )
    entries = split_numbered(text)
    assert len(entries) == 3
    assert entries[0].startswith("Perdana Menteri") and entries[2].endswith("Abdul Rahman Bin Mohamad")
    assert split_numbered("1. Tuan A (Seat X) 2. Tuan B (Seat Y)") == ["Tuan A (Seat X)", "Tuan B (Seat Y)"]


def test_vercel_backend_requirements_match_the_docker_ones() -> None:
    # backend/requirements.txt must sit inside the service root for Vercel, so it is a copy: keep the two in step.
    root = Path(__file__).resolve().parents[1]
    assert (root / "backend" / "requirements.txt").read_text() == (root / "deploy" / "requirements.txt").read_text()
