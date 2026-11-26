"""Turn exceptions into something a visitor can act on.

A dead or paused vector database used to surface as `ResponseHandlingException: [Errno 104] Connection reset by peer`,
which tells a visitor nothing. Database trouble gets one plain sentence; anything else keeps its type and message,
because hiding an unknown error is worse than showing it.
"""

from __future__ import annotations

try:
    from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

    _QDRANT_ERRORS: tuple[type[BaseException], ...] = (ResponseHandlingException, UnexpectedResponse)
except ImportError:  # qdrant-client is a hard dependency; this keeps odd test setups importable
    _QDRANT_ERRORS = ()

DB_DOWN = "Pangkalan data carian tidak dapat dihubungi buat masa ini. Sila cuba lagi sebentar nanti."


def is_database_error(e: BaseException) -> bool:
    return isinstance(e, (*_QDRANT_ERRORS, ConnectionError, TimeoutError))


def friendly_error(e: BaseException) -> str:
    return DB_DOWN if is_database_error(e) else f"{type(e).__name__}: {e}"
