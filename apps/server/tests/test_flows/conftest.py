from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


class FakeFuture:
    def __init__(self, value=None, error: Exception | None = None):
        self._value = value
        self._error = error

    def result(self):
        if self._error is not None:
            raise self._error
        return self._value


class FakeTask:
    def __init__(self, value=None, error: Exception | None = None):
        self.value = value
        self.error = error
        self.submit_calls: list[tuple] = []

    def submit(self, *args, **kwargs):
        self.submit_calls.append((args, kwargs))
        return FakeFuture(self.value, self.error)


class FakeMonitor:
    @contextmanager
    def measure(self, _name: str):
        yield

    def print_summary(self):
        return None


@pytest.fixture
def fake_logger():
    logger = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    logger.debug = MagicMock()
    return logger


@pytest.fixture
def fake_checkpoint_record_factory():
    def _factory(data=None, stage: str = "stage1", stage_status: str = "processing"):
        return SimpleNamespace(
            checkpoint_data=data,
            stage=stage,
            stage_status=stage_status,
            retry_count=0,
            error_message=None,
            can_retry=lambda: True,
        )

    return _factory
