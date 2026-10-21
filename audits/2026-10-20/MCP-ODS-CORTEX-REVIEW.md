# MCP, ODS, OpenWork and Cortex review

Observed 20 October 2026, approximately 22:24–22:28 UTC. This is an integration
review, not a completed deployment or a visual PWA acceptance report.

**Verdict: components are running, but the requested shared, self-maintaining
Cortex and functional PWA are not delivered.** The storage repair is prepared
and backed up, but deployment is blocked by a Docker Desktop engine failure.
The highest priority remains the storage boundary, followed by durable client
memory access and mobile routing.

## Requested outcomes

| Outcome | Current result |
|---|---|
| Shared MCP setup and configuration | Partial: Codex and ODS OpenCode connect to Conductor; canonical policy and role generation exist. Other clients do not automatically inherit them. |
| Orchestration | Partial: Hermes has a bounded Kanban pilot; its drafts remain under review and it has no live Cortex bridge. |
| OpenWork desktop wired into ODS | Not established: selected desktop workspace is local, has no remote engine URL, and its runtime MCP object is empty. The newer Conductor plan parks OpenWork. |
| Styled, functional PWA | Incomplete: mobile HTML, CSS, manifest, icon and service worker exist; all five mobile navigation targets escape the published prefix and return 404. Visual, installation and phone acceptance are blocked/unperformed. |
| All clients maintain shared memory | Not delivered: advertised Conductor tools are read-only; knowledge stores disagree; saved chat-memory tables are empty. |

## Verified working components

- Docker reports `secondbrain-cortex`, `secondbrain-dashboard`, Hermes and the
  ODS model/embedding services running and healthy. These are container checks,
  not proof of ingestion, memory persistence, inference quality or UI behavior.
- Current ODS installation is `/home/chris/ods` in **Ubuntu-24.04**. The older
  host document names Ubuntu-26.04 and contains obsolete routes/service states.
- The actual connected Codex Conductor tools returned policy, source counts
  and a source-backed search result. Policy revision is
  `60603a69c002b411d92d5c20c76b71e64d13a7f1ca420d6de050820bbf7207cc`.
- OpenCode on `127.0.0.1:3003` reports healthy, version `1.18.32`, with
  Conductor `connected`. Its live agent list includes operator, sysop,
  project-manager, personal-assistant, personal-life, Scouts, Cadets and RemapIQ.
- Tailnet HTTPS serves `/cortex/mobile`, `/cortex/search`, the manifest and
  service-worker script with HTTP 200. `/cortex` proxies to loopback port 8765.
- The existing hourly Conductor heartbeat is active. Its latest evidence
  records the storage error rather than silently declaring full acceptance.
- A daily backup of `brain.db` exists. The latest heartbeat reports successful
  integrity and search checks of that backup. This review inspected that
  evidence; it did not perform another restore drill.

## Findings, ordered by impact

### 1. Critical: worker storage is unreadable through its container mount

Fresh read-only checks inside `secondbrain-cortex` produced:

```text
brain.db: quick_check=ok, files=12, chunks=73
index.db: disk I/O error, code=522, SQLITE_IOERR_SHORT_READ
```

The Windows host can read both databases. Existing monitoring also reports
host integrity checks passing while the container read fails. This establishes
a host/container storage-access defect; it does **not** establish corruption.
Do not delete, rebuild or merge either database on this evidence.

The worker healthcheck only tests whether `/data/cortex` is a directory.
Consequently Docker's healthy status does not detect this failure. Use a
readable authoritative database plus recent worker progress for readiness.

### 2. Critical: there are three separate knowledge views

| Consumer | Actual database/view | Sources | Chunks |
|---|---|---:|---:|
| Conductor MCP/CLI | `data/cortex/brain.db` | 12 | 73 |
| Ingestion worker | `data/cortex/index.db` | 1 | 1 |
| Dashboard | `/tmp/cortex-dashboard/index.db` startup copy | 1 | 1 |

Conductor hardcodes `brain.db`; the reused engine's `Config.db_path` chooses
`index.db`. The dashboard uses `shutil.copy2` once at startup and redirects its
database connections to that copy. This is not a WAL-consistent SQLite backup
and does not refresh with ingestion. Database mutations routed to the copy
are disposable and can disappear when the container is recreated.

The daily CLI backup covers the 12-source Conductor store. It does not thereby
cover the worker's separate index, dashboard-only changes or scheduler state.
The current dashboard must not be accepted as a durable editing surface.

### 3. High: shared memory maintenance is unavailable to connected clients

The six enabled Conductor tools are:

```text
conductor_policy, conductor_check_action, conductor_ods_status,
cortex_status, cortex_search, cortex_source
```

None writes facts, conversations, decisions or commitments. The underlying
second-brain engine implements `remember_fact`, `recall_memories` and chat
continuity, but those tools are not exposed by this Conductor connection.

Both databases have **zero** `chat_memories`, `chat_conversations` and
`chat_messages` rows. This does not exclude separate native client memories;
it demonstrates no saved chat memory in these two engine stores at inspection.

Codex's native memory feature is enabled, but its private memory files are a
separate system. Hermes board comments and second-cortex's independent runtime
are also not evidence of writes into this shared knowledge store.

Required repair: one authoritative store and a narrow, auditable write API
using the existing engine, with provenance, stable IDs, deduplication, explicit
update/delete semantics and role permissions. Client session-start retrieval
and session-end writeback must be tested, not merely described in prompts.
Keep credentials and incidental tool output out of durable memory. Do not
solve this by giving every client the engine's entire unrestricted tool set.

### 4. High: the PWA's primary navigation fails on its deployed URL

The actual `/cortex/mobile` HTML links to `/`, `/search`, `/entities`,
`/folders` and `/health`. All five targets return 404 on the tailnet host.
The prefixed `/cortex/search` route returns 200. This is a routing integration
failure, not a failed web server.

The reused dashboard also contains root-relative links/forms/fetches. Repair
the whole request/URL contract under `/cortex`, including redirects and assets;
changing the mobile cards alone is insufficient.

The source repair now changes the mobile shortcut links to relative URLs so the
published `/cortex` prefix is retained, and upgrades the service-worker cache
with old-cache cleanup and navigation-only offline fallback. This is staged in
Conductor source but was not deployed because Docker Desktop lost its engine
after the image export.

Source inspection finds further unfinished PWA behavior:

- Service-worker fetch handling covers every GET and falls back to mobile
  HTML on network failure, including API and asset requests. That can disguise
  failure as the wrong content type. Restrict fallback to app navigation and
  use explicit API/offline errors.
- The worker caches the mobile shell, manifest and SVG icon; it does not
  intentionally cache personal search results. Preserve that privacy boundary.
- There is no old-cache cleanup/update flow. Only an SVG icon is declared;
  phone/browser installation compatibility remains to be tested.
- Registration errors are swallowed. Add a useful install/update/offline state.
- Mobile styling exists in source, but no screenshot, keyboard, touch,
  contrast or responsive-layout acceptance was possible in this run.

Both browser-control entry points failed with `failed to write kernel assets:
The system cannot find the path specified. (os error 3)`. No screenshots were
captured. This technical review is not a visual UX or accessibility audit.

### 5. High: remote dashboard writes need an explicit origin and durability contract

The reused origin guard accepts string prefixes `http://127.0.0.1` and
`http://localhost`; it does not recognize the actual tailnet HTTPS origin.
Legitimate remote mutations may therefore fail. Prefix checks also fail to
compare the complete scheme/host/port and can match lookalike hostnames.

Use parsed, exact trusted origins and appropriate CSRF protection. Verify
every enabled mutation against the authoritative store. Do not relax origin
checks globally to make the phone UI work. No mutation or attack was submitted
as part of this review; this finding is based on the inspected implementation.

### 6. High: OpenWork is not the connected ODS client

The selected workspace is `OpenWork Chat`, a local Windows directory. Its
stored remote base URL is null; its project JSONC only declares a schema.
OpenWork's generated runtime configuration contains `mcp: {}`. A local engine
instance record exists, but the record alone does not establish a running,
connected desktop session or local ODS inference.

ODS OpenCode is separately connected and exposes the generated roles. That
does not wire the desktop application into it. The 19 October Conductor plan
explicitly parks OpenWork; older client notes are marked historical.

To meet the original desktop requirement, onboard the intended workspace to
the supported ODS engine, then verify in the actual UI: selected engine,
provider/model, connected Conductor, policy retrieval and a cross-session
memory write/recall. No workspace or desktop settings were changed in this audit.

### 7. Medium: policy sharing exists, enforcement and client coverage are partial

Canonical policy lives in Conductor's `config/operator-policy.yaml` and
`config/roles/`. The generator creates native OpenCode projections; the
heartbeat reports their current revision. Live roles are advertised.

Codex uses a global MCP definition with an explicit six-tool allowlist;
OpenCode uses project JSON and generated native agent files. OpenWork's local
workspace has no equivalent connection. Hermes pilot profiles consume staged
policy/evidence packets, not a live shared Cortex feed.

MCP instructions do not enforce permissions on unrelated native tools. Current
role projections deny edit/bash/external-directory access, but fresh-session
negative tests are still needed for the full client surface and role binding.
All OpenCode roles currently reach the same MCP server bound to `operator`.

The CDNet HTTP MCP entry exists in Codex config. This review did not establish
its advertised tools, OAuth state, authorization boundary or a Conductor bridge.
Absence of inline authentication headers does not prove absence of OAuth.

Official OpenAI documentation confirms that Codex stores MCP configuration in
its own configuration and supports tool allowlists. It does not imply automatic
sharing with OpenWork or Hermes:
https://learn.chatgpt.com/docs/extend/mcp?surface=cli

### 8. Medium: Hermes orchestration is a bounded pilot

Live board inspection shows PM task `t_c86b3d4e` and sysop task `t_48f5ad7c`
in review; missing-access test `t_07cedc50` is blocked. The bootstrap runbook
records persistence guards and unresolved draft-quality findings. Those drafts
are not accepted policy or completed specialist delivery.

The pilot deliberately limits workers to task-lifecycle tools. It receives
timestamped evidence packets and has no live Conductor retrieval bridge or
automatic evidence refresh. Runtime timeout/restart/retry acceptance and useful
source-backed specialist workflows remain separate outstanding gates.

### 9. Medium: running schedules and source connectors are not fully operational

Worker metadata contains 20,064 scheduler records: 15,592 success, 4,470 failure,
and two without a completed success flag at inspection. The latest recorded
runs include failures for daily brief/digest, voice profile, index snapshot,
Oura and Todoist. A success flag can also represent a disabled/no-op connector;
it does not establish fresh imported records.

Conductor's runtime configuration explicitly disables Gmail and Drive.
Bounded historical imports are not unattended synchronization. No new source
authorization, mailbox import, cloud request or credential provisioning was
performed. Complete source-scoped OAuth and refresh acceptance only after the
shared-store and recovery gates are met.

### 10. Medium: network and documentation have drifted

Current Docker publishing includes all-interface ports 3000 (Open WebUI) and
3011 (ODS dashboard), in addition to proxy port 80. This contradicts the local
documented rule that only the proxy binds all interfaces. A bind alone does not
prove firewall reachability, missing application authentication or WAN exposure.
Reconcile the intended exposure and verify from another LAN device before any
change. No ports, firewall rules, routes or authentication were changed.

Windows Tailscale currently publishes Cortex under `/cortex`, plus named
Hermes and Open WebUI service routes. Older root-dashboard and numbered-port
instructions are not current routing evidence. Root `/` on the Cortex host
returns 404. This review did not establish LAN-wide DNS or pre-login reboot
recovery. `STATUS.md` also incorrectly says no deployment exists.

Windows Conductor imports the editable second-brain source checkout, while the
Dockerfile pins a separate upstream commit and applies a patch. Configuration,
engine/schema compatibility and deployed image/source versions need explicit
acceptance before storage consolidation.

## Repair order and concrete completion gates

1. **Preserve and reconcile storage.** Take separate online SQLite backups of
   both stores; verify them. Choose the authoritative database and supported
   host/container access method, preferably Linux-backed SQLite storage. Retain
   provenance and original stores. Prove fresh worker ingestion is visible in
   MCP and dashboard without restarts, including updates/deduplication.
2. **Make recovery and readiness meaningful.** Back up the actual authoritative
   store/config/state, restore to isolation and test search. Detect wrong-store,
   stale-worker and unreadable-mount failures. Extend the existing heartbeat.
3. **Expose controlled memory maintenance.** Reuse engine memory primitives;
   bind role permissions server-side. Write a synthetic fact from each supported
   client, update it idempotently, recall it in a fresh session and after restart,
   and verify unauthorized mutations are rejected and audited.
4. **Finish `/cortex` and PWA behavior.** Repair all navigation/forms/fetches,
   exact origins and durable writes; finish offline/update behavior. Capture
   desktop/mobile screenshots and verify phone installation and keyboard/touch
   use against the same fresh records as MCP.
5. **Complete client/orchestrator acceptance.** Explicitly resolve OpenWork's
   parked state before onboarding it. Verify live model/engine/tool selection,
   canonical policy refresh, Hermes evidence access and reviewed deliverables.
6. **Enable approved sources last.** Verify bounded Gmail/Drive imports,
   identities, scopes, unattended refresh, revoked tokens and recovery coverage.

These largely match Conductor's existing R1–R6 plan. A replacement framework,
dashboard or scheduler is unnecessary. Use the existing engine and services.

## Evidence, scope and reproducibility

- `database-metadata.json`: fresh metadata-only Windows reads; no source bodies.
- `read_only_inventory.py`: reproducible source/chunk/memory/scheduler counts.
- `container_inventory.py`: read-only quick-check through worker mount paths.
- Direct HTTP GETs checked local/tailnet routes and OpenCode health/MCP/agents.
- Docker inventory/mount inspection and Hermes native Kanban list were read-only.
- Relevant implementation: Conductor `server.py`, `cortex.py`, `settings.py`,
  `dashboard_app.py`, Compose, policy generator, runtime TOML and engine
  `config.py`/`mcp_server.py`/dashboard origin guard.
- Existing backup/pilot evidence was read with its timestamp and provenance;
  it was not presented as a new restore or inference test.
- The two stores were backed up online and reopened successfully. Conductor
  source/config/Compose changes were made to select `brain.db` and remove the
  dashboard startup copy; the PWA source links/service-worker were repaired.
  The rebuilt image passed both patch applications and package build, but the
  Docker engine dropped its connection while exporting, so services were not
  restarted and no live database was overwritten. A clean Docker Desktop
  process restart still failed; the backend log records WSL bootstrap failing
  to format data disk `/dev/sde` (`mkfs` exit status 1).
- No migration merge, source import, memory write, external message or
  credential change occurred. The original `index.db` and `brain.db` remain in
  place, with new verified backups under `data/cortex/recovery-drills`.
- The focused config test passed (`4 passed`), both repositories passed
  `git diff --check`, and AST parsing passed for the changed Python files. The
  documented second-brain `.venv/Scripts/python.exe` is absent; the existing
  Conductor venv ran the checks. Existing user changes were left in place.

No claim is made that all MCP servers, every provider, the visible PWA or every
client's private memory were exhaustively tested. The observed failures are
enough to reject end-to-end completion of the requested integrated setup.

## Follow-up repair and acceptance — 21 October 2026

The Docker failure was repaired without purging the Cortex data disk. The
121 GB `docker_data.vhdx` was copied to `docker_data.vhdx.pre-repair` and
mounted read-only; it contained a valid ext4 filesystem with Docker data
directories. The small Docker system distro was backed up to
`docker_main_ext4.vhdx.pre-repair`, recreated, and Docker Engine 29.8.2
returned. The Cortex and dashboard images were rebuilt and redeployed; both
containers are healthy.

Acceptance then passed: local `/healthz` and tailnet `/cortex/mobile` returned
200; `/cortex/`, `/cortex/search`, `/cortex/entities`, `/cortex/folders`,
`/cortex/health`, the manifest and service worker all returned 200. The mobile
HTML now uses prefix-safe relative links and the deployed service worker is
`cortex-shell-v2` with navigation-only fallback. A fresh stdio MCP session
listed `remember_fact` and `recall_memories`, wrote a marker fact, and recalled
it successfully. Cortex status remains 12 files and 73 chunks, with search
working again.

### OpenWork MCP wiring — 21 October 2026

OpenWork Chat is now registered through its authenticated local control plane rather than by editing the generated runtime file. Workspace `ws_746e31504776` reports the `conductor` MCP entry from `config.remote` as `connected` after an engine reload. The fresh Conductor MCP session exposes `conductor_check_action`, `conductor_ods_status`, `conductor_policy`, `cortex_search`, `cortex_source`, and `cortex_status`; the policy reports the expected operator role and read-only execution boundary.

### OpenWork memory write bridge — 21 October 2026

The OpenWork Conductor MCP now exposes `remember_fact` and `recall_memories` over the shared Cortex database. Writes are bounded to fact/preference/context memory records, redacted recall is enforced, and each write records an audit receipt under the Cortex events directory. The operator policy now permits `memory_write` while retaining approval gates for host, credential, security, network, external communication, cloud inference, paid-service, and destructive actions. A fresh OpenWork MCP session wrote and recalled `OpenWork Cortex bridge acceptance marker` successfully after the rebuilt containers came healthy.
