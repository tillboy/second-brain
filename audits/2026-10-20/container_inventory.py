"""Read only counts and integrity through the worker's own filesystem path."""

import json
import sqlite3
from pathlib import Path

results = {}
for name in ("brain.db", "index.db"):
    item = {}
    conn = None
    try:
        conn = sqlite3.connect(Path("/data/cortex", name).as_uri() + "?mode=ro", uri=True, timeout=3)
        conn.execute("PRAGMA query_only=ON")
        item["integrity"] = conn.execute("PRAGMA quick_check").fetchone()[0]
        item["files"] = conn.execute("SELECT count(*) FROM files").fetchone()[0]
        item["chunks"] = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
    except sqlite3.Error as exc:
        item.update(error=str(exc), error_code=getattr(exc, "sqlite_errorcode", None), error_name=getattr(exc, "sqlite_errorname", None))
    finally:
        if conn is not None:
            conn.close()
    results[name] = item
print(json.dumps(results, indent=2))
