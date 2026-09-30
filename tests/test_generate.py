"""Answering: provider fallback and the verbatim-quote check. No network; placeholder text only."""

from collections.abc import Iterator

import pytest

from tanyadewan.config import GenerateConfig, ProviderConfig
from tanyadewan.generate import llm
from tanyadewan.generate.answer import unverified_quotes
from tanyadewan.generate.prompt import build_messages


class Fake:
    def __init__(self, name: str, pieces: list[str], fail_at: int | None) -> None:
        self.name, self.pieces, self.fail_at = name, pieces, fail_at

    def stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        for i, p in enumerate(self.pieces):
            if i == self.fail_at:
                raise llm.LLMError("free limit reached")
            yield p
        if self.fail_at is not None and self.fail_at >= len(self.pieces):
            raise llm.LLMError("free limit reached")


def chain(monkeypatch, *fakes: Fake) -> llm.FallbackLLM:  # type: ignore[no-untyped-def]
    it = iter(fakes)
    monkeypatch.setattr(llm, "make", lambda p, g: next(it))
    provs = tuple(ProviderConfig(f.name, "openai_compatible", "u", "m", "", "") for f in fakes)
    return llm.FallbackLLM(GenerateConfig(provs, 0.1, 100, 100, 4))


def test_falls_back_before_any_text(monkeypatch):  # type: ignore[no-untyped-def]
    f = chain(monkeypatch, Fake("A (One)", ["x"], fail_at=0), Fake("B (Two)", ["LOREM ", "IPSUM"], None))
    assert "".join(f.stream([])) == "LOREM IPSUM"
    assert f.used.startswith("B (Two), because One free limit reached")


def test_never_mixes_two_models_in_one_answer(monkeypatch):  # type: ignore[no-untyped-def]
    f = chain(monkeypatch, Fake("A (One)", ["LOREM ", "IPSUM"], fail_at=1), Fake("B (Two)", ["DOLOR"], None))
    out = []
    with pytest.raises(llm.LLMError, match="mid-answer"):
        for piece in f.stream([]):
            out.append(piece)
    assert out == ["LOREM "]


def test_all_down(monkeypatch):  # type: ignore[no-untyped-def]
    f = chain(monkeypatch, Fake("A (One)", [], fail_at=0), Fake("B (Two)", [], fail_at=0))
    with pytest.raises(llm.LLMError, match="every free provider"):
        list(f.stream([]))


SOURCES = [{"text": "MP_A said LOREM IPSUM DOLOR SIT AMET consectetur adipiscing."}]


def test_verbatim_quotes_pass_and_paraphrases_are_flagged():
    ok = 'MP_A said "LOREM IPSUM DOLOR SIT AMET" [1].'
    assert unverified_quotes(ok, SOURCES, 4) == []
    bad = 'MP_A said "LOREM IPSUM DOLOR SIT FOREVER" [1].'
    assert unverified_quotes(bad, SOURCES, 4) == ["LOREM IPSUM DOLOR SIT FOREVER"]
    elided = 'MP_A said "LOREM IPSUM ... AMET consectetur adipiscing" [1].'
    assert unverified_quotes(elided, SOURCES, 4) == []
    short = 'the word "LOREM" [1]'  # under min_quote_words: not checked
    assert unverified_quotes(short, SOURCES, 4) == []


def test_prompt_carries_neutrality_rules_and_numbered_sources():
    src = {"speaker_raw": "Tuan MP_A [Kawasan_A]", "sitting_date": "2099-01-02", "section": "motion",
           "page_label_start": "7", "is_draft": True, "text": "LOREM IPSUM"}  # fmt: skip
    msgs = build_messages("Siapa betul?", [src, {**src, "unattributed": True}], 100)
    system, user = msgs[0]["content"], msgs[1]["content"]
    assert "do not judge who is right" in system and "character for character" in system
    assert "[1] Tuan MP_A [Kawasan_A] · 2 Januari 2099" in user and "DRAFT" in user
    assert "[2] a Member (unnamed in the record)" in user
