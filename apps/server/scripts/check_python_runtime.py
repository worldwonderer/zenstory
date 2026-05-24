"""Runtime dependency checks for the backend Python interpreter."""

from __future__ import annotations

import importlib
import sys

REQUIRED_EXPAT_PREFIX = "expat_"


def check_pyexpat() -> str:
    """Validate that Python's pyexpat extension can load its Expat runtime."""
    try:
        pyexpat = importlib.import_module("pyexpat")
    except ImportError as exc:
        raise SystemExit(
            "Broken Python runtime: failed to import pyexpat. "
            "On macOS/Homebrew this usually means pyexpat is linked against "
            "the system /usr/lib/libexpat.1.dylib instead of Homebrew expat. "
            f"Interpreter: {sys.executable}. Original error: {exc}"
        ) from exc

    version = getattr(pyexpat, "EXPAT_VERSION", "")
    if not isinstance(version, str) or not version.startswith(REQUIRED_EXPAT_PREFIX):
        raise SystemExit(
            "Broken Python runtime: pyexpat imported but reported an unexpected "
            f"Expat version {version!r}. Interpreter: {sys.executable}."
        )

    return version


def main() -> int:
    expat_version = check_pyexpat()
    print(f"pyexpat {expat_version}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
