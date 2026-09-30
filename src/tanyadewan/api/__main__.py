"""Run the API + web UI: uv run python -m tanyadewan.api  (http://127.0.0.1:8766)"""

from __future__ import annotations

import os

import uvicorn

from tanyadewan.config import ROOT, load_config


def load_dotenv() -> None:
    """Secrets via .env only (CLAUDE.md). Minimal KEY=VALUE reader; real env vars win."""
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip() and not key.lstrip().startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip('"'))


def main() -> None:
    load_dotenv()
    cfg = load_config().api
    print(f"TanyaDewan is listening on http://{cfg.host}:{cfg.port}. Order, order!")
    uvicorn.run("tanyadewan.api.main:app", host=cfg.host, port=cfg.port, log_level="warning")


if __name__ == "__main__":
    main()
