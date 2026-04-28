from __future__ import annotations

import pytest
from fastapi import Request

from core.error_codes import ErrorCode
from core.error_handler import APIException, api_exception_handler, general_exception_handler


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/wave-d",
            "headers": [],
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 12345),
            "query_string": b"",
        }
    )


def test_api_exception_accepts_message_alias_and_extra_kwargs():
    exc = APIException(
        error_code=ErrorCode.VALIDATION_ERROR,
        message="Friendly message",
        unused="ignored",
    )

    assert exc.detail == "Friendly message"
    assert exc.error_code == ErrorCode.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_api_exception_handler_surfaces_error_detail():
    response = await api_exception_handler(
        _request(),
        APIException(error_code=ErrorCode.NOT_FOUND, detail="Missing entity"),
    )

    assert response.status_code == 400
    assert response.body == b'{"detail":"ERR_NOT_FOUND","error_code":"ERR_NOT_FOUND","error_detail":"Missing entity"}'


@pytest.mark.asyncio
async def test_general_exception_handler_returns_500_payload():
    response = await general_exception_handler(_request(), RuntimeError("boom"))

    assert response.status_code == 500
    assert b'"detail":"ERR_INTERNAL_SERVER_ERROR"' in response.body
