"""Bounded, metadata-only inventory for the MCP/Cortex integration review."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def inventory_database(path):
    result = {"path": str(path), "exists": path.is_file()}
    if not path.is_file():
        return result
    conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=3)
    try:
        conn.execute("PRAGMA query_only=ON")
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        result["counts"] = {}
        for table in ("files", "chunks", "chat_memories", "chat_conversations", "chat_messages", "scheduler_runs", "ai_audit_log"):
            if table in tables:
                result["counts"][table] = conn.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
        if "files" in tables:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(files)")}
            if "indexed_at" in columns:
                result["latest_indexed_at"] = conn.execute("SELECT max(indexed_at) FROM files").fetchone()[0]
            if "source" in columns:
                result["source_counts"] = dict(conn.execute("SELECT source, count(*) FROM files GROUP BY source"))
        result["memory_tables"] = sorted(t for t in tables if "memor" in t or "chat" in t)
        result["scheduler_tables"] = sorted(t for t in tables if "schedul" in t or "job" in t)
        if "scheduler_runs" in tables:
            result["scheduler_columns"] = [row[1] for row in conn.execute("PRAGMA table_info(scheduler_runs)")]
            result["scheduler_totals"] = [list(row) for row in conn.execute("SELECT success, count(*) FROM scheduler_runs GROUP BY success")]
            result["recent_jobs"] = [list(row) for row in conn.execute("SELECT job_name, success, max(started_at) FROM scheduler_runs GROUP BY job_name ORDER BY job_name")]
    except sqlite3.Error as exc:
        result["error"] = str(exc)
    finally:
        conn.close()
    return result


root = Path(r"D:\source\projects\ods-conductor")
report = {
    "observed_at": datetime.now(timezone.utc).isoformat(),
    "databases": [inventory_database(root / "data/cortex" / name) for name in ("brain.db", "index.db")],
}
for module_name in ("secondbrain", "conductor"):
    module = __import__(module_name)
    report[module_name + "_module"] = str(module.__file__)
print(json.dumps(report, indent=2))
