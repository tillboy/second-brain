# Second-brain / ODS status

Updated: 2026-10-21

## Executive summary

The ODS Docker deployment is live on the Windows 11 host. `secondbrain-cortex`,
`secondbrain-dashboard`, `ods-conductor-mcp`, and `ods-hermes` are healthy.
Cortex is running in Docker with the ODS embedding service, and Hermes is
connected to the internal Conductor MCP. The project is integrated enough for
bounded policy, retrieval and memory tests, but the full delivery plan is not
The deployment is operational but the project is not complete. The remaining
delivery gates are tracked in the ODS Conductor `PLAN.md` and acceptance matrix.

## Verified now

- Shared Conductor Cortex database: `brain.db` in the Linux-backed Docker
  volume `ods-cortex-data`.
- Cortex status: 13 indexed files and 74 chunks after legacy reconciliation.
- Hermes MCP: `ODS Conductor` enabled with 8 selected tools.
- Hermes profiles: `conductor-pm` and `conductor-sysop`.
- Fresh policy call, synthetic memory write and recall: passed; the corrected
  stdio acceptance also reports `index_status` at 13 files/74 chunks instead
  of silently opening an empty default database.
- A live Windows bind-mounted SQLite `disk I/O error` was reproduced, raw
  rollback copies were taken, stale sidecars were repaired, and both databases
  then passed integrity checks. A staged Linux-backed Docker volume also passed
  online SQLite backup and restore checks; live services now use that volume.
- A post-cutover backup was restored into an isolated volume and matched live
  aggregate counts: `brain.db` 13 files/74 chunks and legacy `index.db` 1/1.
- The one non-overlapping legacy review record was imported through the
  supported indexer into `brain.db` with a documented ID mapping; the legacy
  store remains preserved.
- The live worker now writes scheduler history to `brain.db` (6,016 runs); the
  legacy store retains 20,121 historical scheduler rows that are intentionally
  preserved pending R2 retention and restore decisions.
- A supported one-shot synthetic ingest/update reached both MCP search and the
  dashboard without restart. The Docker Desktop bind-mounted watcher did not
  observe a host-created file during the short acceptance window. The daemon
  now includes a five-minute `watched_folder_rescan` fallback; live deployment
  and a post-rollout host-created-file check remain open.
- Hermes bridge retry `t_1fa3a1ea` reached review with stored tool receipts;
  bootstrap-mode restrictions still require human review.
- OpenWork authenticated MCP registration and shared-memory acceptance: passed
  in the 2026-10-20 audit evidence.
- PWA/tailnet routes and service health: responding; phone installation,
  offline/update behavior and visible logged-in UI acceptance remain open.
- Google connectors: source-scoped support exists, but account authorization
  and unattended refresh remain intentionally gated.

## Remaining delivery gates

1. Reconcile scheduler ownership/state and prove one authoritative record set;
   the legacy review record import is complete, but the legacy store remains
   preserved pending rollback and freshness acceptance.
2. Complete backup/restore coverage for the authoritative store, protected
   configuration, worker state, and Hermes task state,
   configuration, worker state and Hermes task state.
3. Finish worker freshness, retrieval parity, restart, rollback and failure
   detection checks.
4. Complete screenshot-backed desktop/mobile PWA acceptance and route checks.
5. Run fresh-client policy and unauthorized-access checks for Codex, OpenWork,
   Hermes and any approved remote MCP client.
6. Approve and validate bounded Gmail/Drive OAuth ingestion, including refresh,
   duplicate, revoke, restart and deletion handling.
7. Deliver tested PM/sysop/briefing/reminder workflows and run the full
   acceptance matrix.

## Runtime notes

The Windows repository does not currently contain `.venv/Scripts/python.exe`;
repository tests and lint therefore need to run through the project container or
an explicitly recreated Windows environment. Do not treat Docker health or HTTP
200 responses as proof of end-to-end acceptance.

See `HOST-ENVIRONMENT.md`, `USER-GUIDE-ODS-CORTEX.md`, and the ODS Conductor
`PLAN.md` for access paths, recovery constraints and the authoritative backlog.
