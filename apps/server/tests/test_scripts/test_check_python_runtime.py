import importlib
import types

import pytest

from scripts import check_python_runtime


def test_check_pyexpat_reports_loaded_expat_version() -> None:
    assert check_python_runtime.check_pyexpat().startswith("expat_")


def test_check_pyexpat_explains_broken_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = importlib.import_module

    def fake_import_module(name: str, package: str | None = None):
        if name == "pyexpat":
            raise ImportError("Symbol not found: _XML_SetAllocTrackerActivationThreshold")
        return real_import(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    with pytest.raises(SystemExit) as exc_info:
        check_python_runtime.check_pyexpat()

    message = str(exc_info.value)
    assert "Broken Python runtime" in message
    assert "pyexpat" in message
    assert "libexpat" in message
    assert "_XML_SetAllocTrackerActivationThreshold" in message


def test_check_pyexpat_rejects_unexpected_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda name: types.SimpleNamespace(EXPAT_VERSION="not-expat"),
    )

    with pytest.raises(SystemExit, match="unexpected Expat version"):
        check_python_runtime.check_pyexpat()
