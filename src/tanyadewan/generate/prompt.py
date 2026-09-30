"""The answering prompt. It encodes the neutrality rules from CLAUDE.md; the humour lives elsewhere."""

from __future__ import annotations

import re
from typing import Any

MONTHS_MS = ["Januari", "Februari", "Mac", "April", "Mei", "Jun", "Julai", "Ogos", "September", "Oktober",
             "November", "Disember"]  # fmt: skip

SYSTEM = """You are TanyaDewan, a reference librarian for the Hansard of Malaysia's Dewan Rakyat.
You report what was said, by whom, and when. Nothing else.

Rules:
1. Use ONLY the numbered sources below. End every sentence that states something from them with its
   citation(s), like [1] or [2][4].
2. Attribute words only to the speaker named in that source's header. Never move words from one speaker
   to another. If a header says "a Member (unnamed in the record)", say exactly that; never guess who.
3. Text inside quotation marks must be copied character for character from a source. Otherwise
   paraphrase WITHOUT quotation marks.
4. Stay neutral: do not judge who is right, do not fact-check against outside knowledge, give no opinion,
   and do not describe MPs or parties with loaded words. If asked who is right or for your view, say
   briefly that you only report what was said, then report each position with citations.
   Do not use headings or bold titles to group speakers. Organise the details by speaker: one short
   paragraph or bullet per speaker, beginning with that speaker's name and the sitting date. Never label
   anyone's words as criticism, attack, complaint, defence or praise.
5. When the sources show different sides, include each side that appears, with its own citations.
6. If the sources do not answer the question, say plainly that the indexed Hansard excerpts don't show it.
   Do not fill gaps from memory. Use no outside knowledge at all, including geography (which state a
   constituency is in), party membership or background facts, unless a source states it.
   Leave out sources that don't answer the question instead of discussing them.
9. Write only the final answer: no drafts, no self-corrections, no notes about your own process.
7. Reply in the language of the question (Bahasa Malaysia, English, or a mix, as the user writes).
   Be concise: a short answer, then details. Mention sitting dates.
8. If a source is marked DRAFT (naskhah belum disemak), mention that its wording may still be revised."""


def date_ms(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{int(d)} {MONTHS_MS[int(m) - 1]} {y}"


def speaker_display(p: dict[str, Any]) -> str:
    if p.get("unattributed"):
        return "a Member (unnamed in the record)"
    if p.get("resolution") == "ocr_unreadable":
        return "an unidentified speaker (name unreadable in the scanned record)"
    return str(p.get("speaker_raw") or "unknown speaker")


def source_header(n: int, p: dict[str, Any]) -> str:
    draft = " · DRAFT (naskhah belum disemak)" if p.get("is_draft") else ""
    section = (p.get("section_heading") or p.get("section") or "").strip()
    return f"[{n}] {speaker_display(p)} · {date_ms(str(p['sitting_date']))} · {section} · page {p.get('page_label_start')}{draft}"


# Short questions have few of the stopwords parse/lang.py counts in speeches; these colloquial question
# words decide it instead ("Minister cakap apa pasal ..." is a Malay question with an English noun).
_MS_Q = frozenset(
    [
        "apa",
        "siapa",
        "bila",
        "bagaimana",
        "macam",
        "mana",
        "kenapa",
        "mengapa",
        "berapa",
        "pasal",
        "cakap",
        "kata",
        "tentang",
        "mengenai",
        "betul",
        "ke",
        "tak",
        "adakah",
        "kah",
        "yang",
        "dan",
    ]
)
_EN_Q = frozenset(
    [
        "what",
        "who",
        "whom",
        "which",
        "when",
        "why",
        "how",
        "did",
        "does",
        "do",
        "say",
        "said",
        "about",
        "the",
        "is",
        "are",
        "was",
        "were",
    ]
)

# Words that frame a question without being its topic; never highlighted in a source snippet.
QUESTION_WORDS = _MS_Q | _EN_Q | frozenset(
    ["dalam", "dengan", "untuk", "oleh", "pada", "ada", "dari", "daripada", "kepada", "mp", "mps", "minister", "ahli", "parlimen", "dewan", "rakyat", "raised", "discussed", "mentioned", "dibincangkan", "dibangkitkan", "dibahaskan", "dibincang", "bincang", "bangkitkan", "sebut", "menyebut", "tahun", "lepas"]
)

LANGUAGE_NOTE = {
    "ms": "The question is in Bahasa Malaysia. Write the whole answer in Bahasa Malaysia.",
    "en": "The question is in English. Write the whole answer in English.",
    "mixed": "The question mixes Bahasa Malaysia and English. Answer in Bahasa Malaysia, keeping the English terms the user used.",
}


def question_language(question: str) -> str:
    """ms / en / mixed, for the answer-language instruction."""
    words = re.findall(r"[a-z]+", question.lower())
    ms, en = sum(w in _MS_Q for w in words), sum(w in _EN_Q for w in words)
    if ms and en and min(ms, en) / (ms + en) >= 0.4:
        return "mixed"
    return "en" if en > ms else "ms"


def build_messages(question: str, sources: list[dict[str, Any]], max_chars: int) -> list[dict[str, str]]:
    blocks = []
    for n, p in enumerate(sources, 1):
        text = str(p.get("text") or "")
        if len(text) > max_chars:
            text = text[:max_chars].rsplit(" ", 1)[0] + " …"
        blocks.append(f"{source_header(n, p)}\n{text}")
    note = LANGUAGE_NOTE[question_language(question)]
    user = "Sources:\n\n" + "\n\n".join(blocks) + f"\n\nQuestion: {question}\n\n{note}"
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
