import httpx
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from tanyadewan.api.errors import DB_DOWN, friendly_error, is_database_error


def test_a_reset_connection_becomes_one_plain_sentence():
    # what a paused Qdrant Cloud cluster looked like to visitors
    e = ResponseHandlingException(ConnectionResetError(104, "Connection reset by peer"))
    assert is_database_error(e)
    assert friendly_error(e) == DB_DOWN
    assert "Errno" not in friendly_error(e)


def test_qdrant_http_errors_count_as_database_trouble():
    e = UnexpectedResponse(503, "Service Unavailable", b"", httpx.Headers())
    assert friendly_error(e) == DB_DOWN


def test_plain_connection_and_timeout_errors_count():
    assert is_database_error(ConnectionResetError())
    assert is_database_error(TimeoutError())


def test_unknown_errors_keep_their_type_and_message():
    # hiding an unknown error would be worse than showing it
    assert not is_database_error(ValueError("boom"))
    assert friendly_error(ValueError("boom")) == "ValueError: boom"
