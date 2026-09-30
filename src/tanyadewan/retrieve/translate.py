"""Cross-lingual retrieval: an English (or mixed) question also searches as its Bahasa Malaysia version.

Most of the Hansard is in BM, and both BM25 and the reranker score an English question against BM text
poorly ("student loans" vs "PTPTN"). One short LLM call rewrites the question in BM; retrieval then runs
both versions and the reranker keeps the better score per passage. This is CLAUDE.md experiment 7 (query
translation on vs off): retrieve.translate_query switches it, and the eval harness reports both.

Retrieval must work without an LLM, so any failure here just means "search with the original question".
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache

from tanyadewan.config import load_config
from tanyadewan.generate.llm import LLMError, get_llm
from tanyadewan.generate.prompt import question_language

log = logging.getLogger("tanyadewan.translate")

PROMPT = (
    "Rewrite this search question in Bahasa Malaysia, the way it would be discussed in Malaysia's Dewan "
    "Rakyat. Keep names, places, acronyms and numbers exactly as written. Output only the rewritten "
    "question, nothing else."
)


@lru_cache(maxsize=512)
def to_malay(question: str) -> str | None:
    """The BM version of an English/mixed question, or None (already BM, or the LLM is unavailable)."""
    if question_language(question) == "ms":
        return None
    cfg = load_config()
    try:
        llm = get_llm(cfg.generate)
        text = "".join(
            llm.stream([{"role": "system", "content": PROMPT}, {"role": "user", "content": question}])
        )
    except LLMError as e:
        log.warning("query translation skipped: %s", e)
        return None
    lines = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip().strip('"“”').splitlines()
    out = lines[0].strip() if lines else ""
    return out if out and out.lower() != question.lower() else None
