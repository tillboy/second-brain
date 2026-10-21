# ODS Cortex user guide

This setup provides three user-facing surfaces that share one Cortex database:

- PWA: `https://win11-ws.blowfish-tilapia.ts.net/cortex/mobile`
- OpenWork Chat: the local OpenWork workspace with the `conductor` MCP enabled
- MCP clients: Conductor for ODS orchestration and Cortex retrieval/memory

## Start here

Open the PWA URL on the LAN or tailnet. Use **Search memory** for source-backed results, **Browse sources** for indexed folders, and **Service health** to confirm the dashboard is responding. Use the browser's **Install app** or **Add to home screen** command for a phone-like shortcut.

OpenWork Chat is already wired to the local ODS Conductor. Its MCP tools include:

- `conductor_policy` — read the current role and approval boundaries first
- `cortex_search`, `cortex_source`, `cortex_status` — retrieve and inspect Cortex data
- `remember_fact`, `recall_memories` — persist and recall cross-session memory
- `conductor_ods_status` — inspect the ODS runtime
- `conductor_check_action` — check whether an operation needs approval

## Memory workflow

Use `remember_fact` for stable facts, preferences, or context. Supply a short key, the content, and one of `fact`, `preference`, or `context`.

Use `recall_memories` with a few distinctive words from the fact. Recall output is redacted before it leaves Cortex. Memory writes are stored in the shared `brain.db` and produce an audit receipt under the Cortex events directory.

The operator role permits bounded `memory_write`. Host administration, credential changes, security changes, destructive operations, public exposure, external communication, cloud inference, and paid-service activation remain approval-gated.

## Health checks

From PowerShell:

```powershell
docker ps --format '{{.Names}} {{.Status}}'
Invoke-WebRequest http://127.0.0.1:8765/healthz -UseBasicParsing
```

For OpenWork MCP status, the desktop control plane reports the `conductor` entry as `connected`. The OpenWork workspace registration is persistent; do not edit the generated runtime JSON directly because OpenWork regenerates it.

## Recovery

If Docker fails to start, preserve the Docker data VHD before attempting any reset. The repair procedure used a byte-copy backup and recreated only Docker's system distro. Do not factory-reset Docker or purge historical data without an explicit retention decision.

If the PWA is unavailable, check Docker health first, then test the local dashboard endpoint. If OpenWork reports a disconnected MCP, reload the workspace engine from OpenWork or restart the desktop app; the registered MCP entry should remain present.

## Evidence and validation

The acceptance record is in `D:\source\projects\second-brain\audits\2026-10-20\deployment-attempt.json`. The review narrative is in `D:\source\projects\second-brain\audits\2026-10-20\MCP-ODS-CORTEX-REVIEW.md`.

The validated commands are:

```powershell
python -m pytest -x -q -m "not slow"   # second-brain: 1466 passed, 1 skipped
python -m pytest -q                     # ods-conductor: 42 passed, 2 skipped
python -m ruff check src tests
```

## Hermes orchestration

Hermes is connected to the internal ODS Conductor MCP at `http://ods-conductor-mcp:8000/mcp`. In Hermes, run `hermes mcp list` and confirm `ODS Conductor` is enabled with 8 selected tools. The profiles are `conductor-pm` (planning and evidence) and `conductor-sysop` (read-only operations). Both are restricted to the Conductor tools, require review, and cannot use terminal, browser, filesystem, connectors, or external communication.

The live task board is `conductor-bootstrap`. Inspect it with:

```powershell
docker exec -u hermes -e HERMES_KANBAN_BOARD=conductor-bootstrap ods-hermes /opt/hermes/.venv/bin/hermes kanban list
```

The task definitions and constraints are documented in [HERMES-ORCHESTRATION.md](HERMES-ORCHESTRATION.md).
