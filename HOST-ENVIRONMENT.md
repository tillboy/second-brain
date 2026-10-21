# Host environment

Where `secondbrain` runs, what else shares that machine, and how the surfaces are reached
from other devices. `secondbrain` itself is local-first and does not need any of this to
work — this file exists so that "the host" is unambiguous when we talk about ports,
reverse proxies, or remote access.

Verified on this host on 2026-10-13, and re-verified 2026-10-15 (commands used are listed in the last section).

---

## 1. The machine

| | |
|---|---|
| Hostname | `DESKTOP-NQH179T` |
| OS | Microsoft Windows 11 Pro, build `26300` |
| LAN address | `192.168.8.225` (interface `Ethernet`) |
| GPU | NVIDIA GeForce RTX 3060, 12 GB |

**Provenance:** this PC replaces the previous `PVE02` Proxmox host, which is now
deprecated. Docker, WSL and ODS all run on this one Windows 11 machine — there is no
longer a separate hypervisor in the path.

## 2. Runtime stack

| Layer | Detail |
|---|---|
| WSL distro | `Ubuntu-26.04`, kernel `6.18.40.1-microsoft-standard-WSL2`, WSL `3.0.1.0` |
| WSL networking | default **NAT** — no `~/.wslconfig`; distro `eth0 = 172.25.3.222/20`, gateway `172.25.0.1` |
| Container runtime | Docker Desktop engine, `29.8.2` (`docker info` → `docker-desktop \| Docker Desktop (containerized)`) |
| Where containers live | Docker Desktop's own VM — **not** the `Ubuntu-26.04` distro. Ports are published on the Windows side (`com.docker.backend.exe` owns `0.0.0.0:80` and `:443`) |
| ODS | `ods-cli v3.0.0`, install root `/home/chris/ods`, `ODS_DEVICE_NAME=desktop-nqh179t` |

Because Docker Desktop publishes container ports on the **Windows** host, a service bound
to `127.0.0.1` inside the container is reachable at `127.0.0.1:<port>` from Windows —
which is what makes `tailscale serve` (running on Windows) able to front it without any
`0.0.0.0` binding.

## 3. ODS services

**Always-on core**

| Service | Published | Purpose |
|---|---|---|
| `dashboard` | `127.0.0.1:3001`, `:3011` | Operator UI; `:3011` is the network listener that always requires sign-in |
| `dashboard-api` | `127.0.0.1:3002` | Admin API + magic-link redemption |
| `open-webui` | `127.0.0.1:3000` | Chat UI |
| `llama-server` | `127.0.0.1:11434` | Local inference |
| `model-router`, `pixel-agent`, `pixel-edge`, `pixel-model-relay` | `:9595`, `127.0.0.1:4006` | Model routing + Pixel sandbox/agent plumbing |
| `remote-provider-egress`, `remote-provider-ssh-tunnel` | internal | Egress + SSH tunnels for remote providers |

**Enabled extensions**

| Service | Published |
|---|---|
| `ods-proxy` | **`0.0.0.0:80`, `0.0.0.0:443`** |
| `ape` | `127.0.0.1:7890` |
| `comfyui` | `127.0.0.1:8188` |
| `embeddings` | `127.0.0.1:8090` |
| `hermes` / `hermes-proxy` | `9119` (internal) / `127.0.0.1:9120` |
| `langfuse` (+ redis/postgres/clickhouse/minio) | `127.0.0.1:3006` |
| `litellm` | `127.0.0.1:4000` |
| `n8n` | `127.0.0.1:5678` |
| `perplexica` | `127.0.0.1:3004` |
| `privacy-shield` | `127.0.0.1:8085` |
| `qdrant` | `127.0.0.1:6333-6334` |
| `searxng` | `127.0.0.1:8888` |
| `token-spy` | `127.0.0.1:3005` |
| `tts` (Kokoro) | `127.0.0.1:8880` |
| `whisper` | `127.0.0.1:9000` |

**Disabled:** `brave-search`, `fooocus`, `opencode`, `pixel-inference`, `tailscale`.

**Exposure rule — important:** `ods-proxy` is the *only* thing bound to `0.0.0.0`.
Everything else stays on loopback on purpose. Widening `BIND_ADDRESS` globally would put
`langfuse-postgres`, `langfuse-redis`, `qdrant` and the admin API on the LAN.

## 4. Access path A — tailnet (works from anywhere)

The Windows host's own `tailscaled` is joined to the tailnet as
**`win11-ws.blowfish-tilapia.ts.net`**, and services are published with
`tailscale serve` (run on Windows, not inside WSL):

| Tailnet URL | Backs onto | Notes |
|---|---|---|
| `https://win11-ws.blowfish-tilapia.ts.net` | `127.0.0.1:3011` | Dashboard; ODS Talk at `/talk` |
| `https://…ts.net:8443` | `127.0.0.1:3000` | Open WebUI |
| `https://…ts.net:8444` | `127.0.0.1:5678` | n8n |
| `https://…ts.net:8445` | `127.0.0.1:3003` | OpenCode |
| `https://…ts.net:8446` | `127.0.0.1:3006` | Langfuse |
| `https://…ts.net:8447` | `127.0.0.1:8188` | ComfyUI |

- **TLS is real:** certificate `CN=win11-ws.blowfish-tilapia.ts.net`, SAN matching, issued
  by Let's Encrypt, valid to 2027-01-11. Validated from the system trust store, not
  `curl -k`.
- **Verified:** `/` 200, `/talk` 200, `/health` 200, `/api/status` 401 (auth enforced).
- **Only tailnet devices can reach these** — no public endpoint, Funnel deliberately off.
- ODS's bundled `tailscale` extension stays **disabled**: it is Linux-only and needs host
  networking, which Docker Desktop on Windows does not provide. `tailscale serve` on the
  host is the working equivalent here.

## 5. Access path B — LAN (no Tailscale client)

`ods-proxy` (Caddy) is the single LAN entry on `http://192.168.8.225:80` and routes by
**Host** header:

| LAN URL | Backend |
|---|---|
| `http://desktop-nqh179t.local` | 302 → `chat.desktop-nqh179t.local` |
| `http://chat.desktop-nqh179t.local` | Open WebUI (`:8080`) |
| `http://dashboard.desktop-nqh179t.local` | Dashboard (`:3011`, sign-in) |
| `http://talk.desktop-nqh179t.local/talk` | ODS Talk mobile owner portal |
| `http://auth.desktop-nqh179t.local` | `dashboard-api` (magic-link redemption) |
| `http://api.desktop-nqh179t.local` | `dashboard-api` admin `/api/*` |
| `http://hermes.desktop-nqh179t.local` | `hermes-proxy` (session-gated) |

**The LAN also serves HTTPS, on `:443`.** `ods-proxy` publishes both `:80` and `:443`; its
compose had reserved 443 for "a future TLS upgrade" and `patch-ods-proxy-tls.py` wired it up
through Caddy's internal CA (`issuer=CN=Caddy Local Authority - ECC Intermediate`), because a
public CA cannot vouch for a `.local` name. Verified from a separate LAN device (`pve01`,
`192.168.8.230`): `chat`, `talk` and `dashboard` all answer `200` on **both** ports. Two
caveats. Each client must trust `ods-local-ca.crt`. And a TLS client **must send SNI**:
`https://192.168.8.225/` with no SNI fails with `tlsv1 alert internal error`, because Caddy
selects the site and certificate by SNI — `curl -H 'Host: …'` is not SNI, so use `--resolve`
or a real hostname. That failure is indistinguishable from a dead listener and is not one.

**Known local defect:** ODS's `ods-mdns` announcer computes the address to advertise with
a "UDP socket to 8.8.8.8" trick, which under WSL2 NAT returns the *distro's* address
(`172.25.3.222`) instead of the host's LAN address (`192.168.8.225`). Its multicast also
stays on the host-internal WSL vSwitch. Net effect: a LAN client with no explicit record
cannot resolve these names.

Current workaround on this host: hosts-file entries pinning the seven names to
`192.168.8.225`, plus an inbound firewall rule for TCP 80 (`ODS Portal (TCP 80)`,
Private profile, local subnet). Verified with those in place:
`http://talk.desktop-nqh179t.local/talk` → 200.

Proper fixes, best first: (1) the upstream `ods-mdns` change to detect WSL and advertise
the Windows host's LAN IPv4, plus an `ODS_MDNS_ADVERTISE_IP` override; (2) switch the
distro to `networkingMode=mirrored`; (3) per-client DNS/hosts records — which cannot help
a phone.

## 6. Selected ODS `.env` settings

| Key | Value | Note |
|---|---|---|
| `ODS_DEVICE_NAME` | `desktop-nqh179t` | Drives every `.local` hostname |
| `BIND_ADDRESS` | `127.0.0.1` | Deliberate: only the proxy is LAN-facing |
| `ODS_PROXY_BIND` | unset → `0.0.0.0` | The proxy's default |
| `ODS_PUBLIC_URL` | `https://win11-ws.blowfish-tilapia.ts.net` | Tailnet-first |
| `ODS_SERVICE_PUBLIC_URLS` | maps open-webui/n8n/opencode/langfuse/comfyui → `:8443`–`:8447` | |
| `ODS_TALK_PUBLIC_URL` | **unset** | Open item — see below |
| `ODS_COOKIE_DOMAIN` | **unset** | `ods-session` is host-only (no cross-subdomain SSO) |

## 7. Where secondbrain fits

- **Current status: Docker deployment is running.** `secondbrain-cortex`,
  `secondbrain-dashboard` and `ods-conductor-mcp` are attached to the ODS network;
  `ods-hermes` connects to the Conductor MCP internally.
- The dashboard remains loopback-published at `127.0.0.1:8765` by design. The
  approved tailnet route is the private `/cortex` path documented in the ODS guide;
  do not rebind the dashboard to `0.0.0.0`.
- Current PWA routes respond, but phone installation, offline/update behavior,
  complete prefix navigation and screenshot-backed logged-in UI acceptance remain
  open project gates.
- Worker, Conductor and dashboard target `brain.db`; the older `index.db` remains
  on disk until the R1 reconciliation and rollback review is complete.

## 8. Open items

1. `ods-mdns` advertises the WSL NAT address (section 5). A full defect report exists;
   it has **not been filed upstream**.
2. `ODS_TALK_PUBLIC_URL` is unset, so mobile owner-card links point at
   `talk.<device>.local`. That name is unresolvable for a phone away from the LAN;
   pointing it at `https://win11-ws.blowfish-tilapia.ts.net/talk` (verified 200) fixes
   the remote-phone flow. **Not applied yet.**
3. `ODS_COOKIE_DOMAIN` unset — each surface signs in separately. Setting it to
   `desktop-nqh179t.local` gives LAN single-sign-on, but a `.local` cookie can never be
   valid for the `ts.net` host, so the tailnet path will always sign in on its own.
4. ~~LAN access is plain HTTP. The tailnet path is the only one with trusted TLS.~~
   **Corrected 2026-10-15:** the LAN now serves HTTPS on `:443` as well as HTTP on `:80`
   (section 5). The tailnet path is still the only one with **publicly trusted** TLS; the LAN
   path uses `ods-local-ca.crt`, which every client must trust.
5. **An unattended reboot is an outage.** Every autostart mechanism on this host is
   logon-triggered and Docker Desktop has no service mode, so a reboot with nobody present
   leaves the whole stack down — 87 minutes of it on 2026-10-14. Either enable auto-logon
   (ideally via an LSA secret rather than the registry) or accept it. **Not decided.**
6. **Alerts do not leave this machine.** `uptime-alerts.log` records every transition and
   `UPTIME-ALERT.txt` exists while something is failing, but nothing is pushed off-host —
   which is how a six-hour ISP outage on 2026-10-15 went unnoticed. Wiring a sender into the
   checker's transition block is the fix. **Parked on request.**

## 9. How to re-verify

```bash
# Host identity
powershell.exe -NoProfile -Command "(Get-CimInstance Win32_OperatingSystem).Caption"

# ODS inventory + exposure
wsl.exe -d Ubuntu-26.04 -- bash -lc "cd /home/chris/ods && ods version && ods list"
wsl.exe -d Ubuntu-26.04 -- bash -lc "docker ps --format '{{.Names}}\t{{.Ports}}'"

# Tailnet publishing + certificate
tailscale.exe serve status
curl -sS -o /dev/null -w '%{http_code} %{ssl_verify_result}\n' https://win11-ws.blowfish-tilapia.ts.net/

# LAN path
curl -s -o /dev/null -w '%{http_code}\n' http://talk.desktop-nqh179t.local/talk

# Every access path in one command - 41 checks across local, tailnet and public,
# plus the dependencies, in about 2.8s when the stack is healthy. This is now the
# fastest way to re-verify sections 3-5. It writes its own record, so it can be run
# any time: see uptime-checks.md for -NoState (observe only) and -StateDir (elsewhere).
powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\Users\Chris\AppData\Local\ODS\ods-uptime-check.ps1

# The same record, without running anything: is anything failing right now?
# Absent = nothing is failing. Present = read it first.
dir C:\Users\Chris\AppData\Local\ODS\UPTIME-ALERT.txt
```

Per the README, `secondbrain` needs no network plumbing of its own: local-first, loopback
dashboard, stdio MCP. Everything in sections 4–5 is about ODS, and is documented here only
so the host is understood as a whole.
