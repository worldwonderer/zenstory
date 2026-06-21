#!/usr/bin/env python3
"""
One-off ops cleanup: delete stale ``compaction_summary`` rows from the
``agent_artifact_ledger`` table.

The LLM-summarization "compaction" subsystem has been removed from the
codebase. Older deployments may still have ``action == "compaction_summary"``
rows that were written by the now-deleted checkpoint persistence logic. These
rows are inert (nothing reads them anymore) but harmless; this script removes
them so the table no longer carries dead artifacts.

Safe to re-run: it only deletes rows whose ``action`` equals
``"compaction_summary"`` and prints how many were removed. If there are none,
it deletes nothing and reports ``0``.

Usage:
    python scripts/cleanup_compaction_summary_rows.py

Honors ``DATABASE_URL`` from the environment (falls back to the local SQLite
dev database, matching the other scripts in this directory).
"""

import os
import sys

# Load .env file
from dotenv import load_dotenv

load_dotenv()

# Use DATABASE_URL from env, fallback to SQLite for local dev
os.environ.setdefault("DATABASE_URL", "sqlite:///./zenstory.db")

# Add parent directory to path so `database` / `models` import cleanly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete, func, select  # noqa: E402
from sqlmodel import Session  # noqa: E402

from database import sync_engine  # noqa: E402
from models import AgentArtifactLedger  # noqa: E402

COMPACTION_SUMMARY_ACTION = "compaction_summary"


def cleanup_compaction_summary_rows() -> int:
    """Delete all compaction_summary ledger rows. Returns the count deleted."""
    with Session(sync_engine) as session:
        count = int(
            session.exec(
                select(func.count())
                .select_from(AgentArtifactLedger)
                .where(AgentArtifactLedger.action == COMPACTION_SUMMARY_ACTION)
            ).one()
        )

        if count:
            session.exec(
                delete(AgentArtifactLedger).where(
                    AgentArtifactLedger.action == COMPACTION_SUMMARY_ACTION
                )
            )
            session.commit()

        return count


def main() -> None:
    deleted = cleanup_compaction_summary_rows()
    print(f"Deleted {deleted} compaction_summary ledger row(s).")


if __name__ == "__main__":
    main()
