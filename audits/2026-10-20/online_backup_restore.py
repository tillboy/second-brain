"""Create and verify online SQLite backups for both Cortex stores.

This script intentionally records metadata only. It never mutates the live
databases and never emits source text.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


def backup_and_verify(source: Path, destination: Path) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    source_uri = source.as_uri() + "?mode=ro"
    source_conn = sqlite3.connect(source_uri, uri=True, timeout=10)
    target_conn = sqlite3.connect(destination, timeout=10)
    try:
        source_conn.execute("PRAGMA query_only=ON")
        source_conn.backup(target_conn)
        integrity = target_conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"backup integrity failed for {source}: {integrity}")
        tables = {row[0] for row in target_conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        counts = {}
        for table in ("files", "chunks", "scheduler_runs", "chat_memories", "chat_conversations", "chat_messages"):
            if table in tables:
                counts[table] = target_conn.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
        # Reopen a second read-only connection to prove the backup is usable.
        target_conn.close()
        target_conn = None
        reopened = sqlite3.connect(destination.as_uri() + "?mode=ro", uri=True, timeout=10)
        try:
            reopened.execute("PRAGMA query_only=ON")
            reopened_integrity = reopened.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            reopened.close()
        if reopened_integrity != "ok":
            raise RuntimeError(f"reopened backup integrity failed for {destination}: {reopened_integrity}")
        return {
            "source": str(source),
            "backup": str(destination),
            "integrity": integrity,
            "reopened_integrity": reopened_integrity,
            "bytes": destination.stat().st_size,
            "counts": counts,
        }
    finally:
        source_conn.close()
        if target_conn is not None:
            target_conn.close()


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"D:\source\projects\ods-conductor\data\cortex")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination_dir = root / "recovery-drills" / f"online-{stamp}"
    results = []
    for name in ("brain.db", "index.db"):
        results.append(backup_and_verify(root / name, destination_dir / name))
    report = {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "destination": str(destination_dir),
        "databases": results,
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
