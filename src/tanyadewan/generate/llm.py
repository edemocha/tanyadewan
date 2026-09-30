"""LLM clients behind one streaming interface, and a fallback chain. Never hardcode a provider (CLAUDE.md).

  openai_compatible   any OpenAI-style API (Groq, Kilo, OpenRouter, …); key from the env var named in config,
                      or none for keyless free tiers
  ollama              a local model via Ollama /api/chat

FallbackLLM tries the configured providers in order. A provider that fails BEFORE writing anything
(rate limit, missing key, outage) is skipped; one that fails mid-answer ends the answer with an error,
because mixing two models' text into one answer would be worse.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any, Protocol

from tanyadewan.config import GenerateConfig, ProviderConfig


class LLMError(RuntimeError):
    pass


class LLM(Protocol):
    name: str

    def stream(self, messages: list[dict[str, str]]) -> Iterator[str]: ...


def _post(url: str, body: dict[str, Any], headers: dict[str, str], timeout: float = 180) -> Any:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        # Some free APIs sit behind Cloudflare, which refuses the default Python User-Agent (error 1010).
        headers={"Content-Type": "application/json", "User-Agent": "TanyaDewan/0.1", **headers},
    )
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            wait = e.headers.get("retry-after")
            raise LLMError("free limit reached" + (f", retry in {wait}s" if wait else "")) from e
        raise LLMError(f"HTTP {e.code}: {e.read()[:200]!r}") from e
    except OSError as e:
        raise LLMError(f"not reachable ({e})") from e


class OpenAICompatibleLLM:
    def __init__(self, p: ProviderConfig, g: GenerateConfig) -> None:
        self.p, self.g = p, g
        self.key = os.environ.get(p.api_key_env, "") if p.api_key_env else ""
        self.name = f"{p.model} ({p.name})"

    def stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        if self.p.api_key_env and not self.key:
            raise LLMError(f"no API key (set {self.p.api_key_env} in .env)")
        body: dict[str, Any] = {"model": self.p.model, "messages": messages, "stream": True,
                                "temperature": self.g.temperature, "max_tokens": self.g.max_tokens}  # fmt: skip
        if self.p.reasoning_effort:
            body["reasoning_effort"] = self.p.reasoning_effort
        headers = {"Authorization": f"Bearer {self.key}"} if self.key else {}
        with _post(f"{self.p.base_url}/chat/completions", body, headers) as resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:") or line == "data: [DONE]":
                    continue
                chunk = json.loads(line[5:])
                if chunk.get("error"):
                    raise LLMError(str(chunk["error"])[:200])
                for choice in chunk.get("choices", []):
                    if piece := (choice.get("delta") or {}).get("content"):
                        yield piece


class OllamaLLM:
    def __init__(self, p: ProviderConfig, g: GenerateConfig) -> None:
        self.p, self.g = p, g
        self.name = f"{p.model} ({p.name}, local)"

    def stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        body = {"model": self.p.model, "messages": messages, "stream": True, "think": False,
                "options": {"temperature": self.g.temperature, "num_predict": self.g.max_tokens}}  # fmt: skip
        with _post(f"{self.p.base_url}/api/chat", body, {}) as resp:
            for line in resp:
                if line.strip():
                    obj = json.loads(line)
                    if obj.get("error"):
                        raise LLMError(str(obj["error"]))
                    if piece := (obj.get("message") or {}).get("content"):
                        yield piece


def make(p: ProviderConfig, g: GenerateConfig) -> LLM:
    if p.kind == "openai_compatible":
        return OpenAICompatibleLLM(p, g)
    if p.kind == "ollama":
        return OllamaLLM(p, g)
    raise LLMError(f"unknown provider kind {p.kind!r}")


class FallbackLLM:
    """Tries each provider in order. After stream() finishes, `used` says who answered and why."""

    def __init__(self, g: GenerateConfig) -> None:
        self.chain = [make(p, g) for p in g.providers]
        if not self.chain:
            raise LLMError("no providers configured (generate.providers in config.yaml)")
        self.name = " → ".join(c.name for c in self.chain)
        self.used = ""

    def stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        skipped: list[str] = []
        for llm in self.chain:
            started = False
            try:
                for piece in llm.stream(messages):
                    started = True
                    yield piece
                self.used = llm.name + (f", because {'; '.join(skipped)}" if skipped else "")
                return
            except LLMError as e:
                if started:
                    raise LLMError(f"{llm.name} stopped mid-answer: {e}") from e
                skipped.append(f"{llm.name.split(' (')[-1].rstrip(')')} {e}")
        raise LLMError("every free provider is unavailable right now: " + "; ".join(skipped))


def get_llm(cfg: GenerateConfig) -> FallbackLLM:
    return FallbackLLM(cfg)
