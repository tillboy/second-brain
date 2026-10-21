# Freebuff instruction: finalise ODS access on the Windows 11 Nvidia host

Date: 2026-10-13

## Context

PVE02 has been binned and must not be treated as the live ODS host.

The Nvidia hosting PC is now running Windows 11 and is the canonical ODS host for this work. Any previous assumptions about Proxmox, Ubuntu VM 201, `/home/cdnet-admin/ods`, PVE02 IPs, or Linux-hosted ODS should be ignored unless re-discovered live on the Windows 11 host.

The ODS access design should be finalised around three deliberately separate access families:

| Audience | Entry | Security boundary |
|---|---|---|
| Tailnet devices | `https://win11-ws.blowfish-tilapia.ts.net` | Tailscale device identity |
| Trusted LAN devices | `http://*.desktop-nqh179t.local` | Trusted LAN plus ODS/Open WebUI app auth |
| Chris's phone outside Tailscale | dedicated HTTPS hostname, for example `https://conduit-ods.cdnet.uk` | mTLS client certificate plus app auth/API key |

Do not use Tailscale Funnel for this. Do not expose raw ODS, Open WebUI, Ollama, n8n, Langfuse, ComfyUI, or Hermes ports directly to the public internet.

## Current proposal to preserve

Keep the Windows-host `tailscaled` plus `tailscale serve` design for tailnet access.

The intended shape is:

```text
Tailnet client
  -> https://win11-ws.blowfish-tilapia.ts.net[:port]
  -> tailscale serve on Windows
  -> 127.0.0.1:<service-port>
  -> Docker Desktop / ODS service
```

Keep `BIND_ADDRESS=127.0.0.1` unless live testing proves a specific service cannot work that way. On Windows plus Docker Desktop, loopback publishing is desirable: `tailscale serve` can reach the Windows loopback, while the services themselves remain unavailable on the LAN/WAN except through the intended proxy layers.

The LAN path should remain through `ods-proxy`/Caddy, using host-based routing:

```text
LAN client
  -> http://*.desktop-nqh179t.local
  -> ods-proxy / Caddy on the Windows ODS stack
  -> container/service backend
```

The tailnet path should not be forced through the LAN `ods-proxy`. Open WebUI and related services should avoid subpath routing unless upstream support is proven, because root-mounted assumptions, OAuth callbacks, and websockets are likely to break behind paths such as `/chat` or `/api`.

## Required changes

### 1. Re-discover the live ODS install location

Before changing files, discover the actual ODS checkout and `.env` location on the Windows 11 host.

Do not assume either of these older paths is correct:

```text
/home/cdnet-admin/ods
/home/chris/ods
```

Record the discovered path in the final status report.

### 2. Set the Talk public URL for remote phone use

If `ODS_TALK_PUBLIC_URL` is unset, set it to the tailnet Talk URL:

```env
ODS_TALK_PUBLIC_URL=https://win11-ws.blowfish-tilapia.ts.net/talk
```

Keep:

```env
ODS_PUBLIC_URL=https://win11-ws.blowfish-tilapia.ts.net
```

unless Chris explicitly chooses LAN-first or Conduit/mTLS-first invitations later.

Restart only the services needed for this setting to take effect, expected to be:

```bash
ods restart dashboard dashboard-api
```

Adjust the command only if live ODS service naming differs.

### 3. Leave cookie domain conservative

Do not set `ODS_COOKIE_DOMAIN` by default.

Reason: `desktop-nqh179t.local` and `win11-ws.blowfish-tilapia.ts.net` are different registrable host families. A single cookie cannot span both. Host-only cookies are the safest default even if they require separate sign-in on separate surfaces.

Only set:

```env
ODS_COOKIE_DOMAIN=desktop-nqh179t.local
```

if Chris explicitly chooses LAN subdomain SSO and accepts that the tailnet family remains separate.

### 4. Fix LAN name resolution separately

If LAN-only devices cannot resolve `*.desktop-nqh179t.local`, treat that as a LAN/mDNS/DNS defect, not a reason to widen ODS service binds.

Expected issue: WSL may advertise an internal NAT address such as `172.x.x.x` instead of the Windows LAN address.

Preferred fixes, in order:

1. Add or use an ODS mDNS advertised-IP override so the LAN advertises the Windows host LAN IPv4.
2. Use router DNS records for the required names if the router supports it cleanly.
3. Consider WSL mirrored networking only after confirming it will not disrupt Docker Desktop or the running ODS stack.

Do not switch all ODS services to `0.0.0.0` to solve name resolution.

### 5. Add non-Tailscale Conduit iOS access with mTLS

Chris wants to use the `cogwheel0/conduit` iOS app from his phone outside Tailscale.

This is the Conduit app at:

```text
https://github.com/cogwheel0/conduit
```

It is a native mobile client for Open WebUI, direct OpenAI-compatible/Ollama endpoints, and Hermes agents. It is not the remote desktop/VNC app also called Conduit.

Create a separate public HTTPS route protected by mutual TLS:

```text
Conduit iOS
  -> https://conduit-ods.cdnet.uk
  -> reverse proxy requiring a trusted client certificate
  -> http://127.0.0.1:<open-webui-or-api-port>
```

Use a hostname agreed with Chris. `conduit-ods.cdnet.uk` is a suggested name, not mandatory.

Requirements:

- mTLS must be enforced before traffic reaches ODS/Open WebUI/Ollama.
- The backend must remain loopback-bound on the Windows host where possible.
- Issue a unique client certificate for Chris's phone.
- Store the private key only on the phone/profile path needed by Conduit/iOS.
- Document the revocation process for the phone certificate.
- Keep normal app-layer auth enabled: Open WebUI login, API key, or other configured auth still applies after mTLS succeeds.
- Do not make this route the default `ODS_PUBLIC_URL` unless Chris explicitly chooses it as the primary invitation/magic-link audience.

Conduit setup target:

```text
Mode: Open WebUI, if full Open WebUI features are wanted
Base URL: https://conduit-ods.cdnet.uk
Auth: Open WebUI login or required API/custom headers
Transport: HTTPS through the mTLS reverse proxy
```

Alternative:

```text
Mode: Direct, if only OpenAI-compatible/Ollama access is wanted
Base URL: https://conduit-ods.cdnet.uk
Auth: API key or required custom headers
Transport: HTTPS through the mTLS reverse proxy
```

Important validation: confirm that the installed Conduit iOS build can present the required iOS client certificate/profile to the chosen reverse proxy. If it cannot, stop and report that limitation rather than weakening the public route.

## Verification gates

Do not report ODS access as finalised until all relevant checks below have been run and the results recorded.

### Tailnet verification

Run from a real second device on the tailnet, not only from the Windows host:

```text
https://win11-ws.blowfish-tilapia.ts.net/
https://win11-ws.blowfish-tilapia.ts.net/talk
https://win11-ws.blowfish-tilapia.ts.net/health
https://win11-ws.blowfish-tilapia.ts.net/api/status
```

Expected:

- Dashboard/main route returns 200 or login page.
- `/talk` loads.
- `/health` returns healthy status.
- `/api/status` enforces auth where appropriate, for example 401 is acceptable if unauthenticated.
- TLS validates without disabling certificate checks.

### LAN verification

Run from a LAN-only device with no Tailscale client:

```text
http://desktop-nqh179t.local
http://talk.desktop-nqh179t.local/talk
http://dashboard.desktop-nqh179t.local/
```

Expected:

- Names resolve to the Windows host LAN address, not a WSL NAT address.
- Routes load through `ods-proxy`.
- No raw service ports are exposed unnecessarily on the LAN.

### Public Conduit/mTLS verification

Run these tests from outside the LAN and outside Tailscale.

Without a client certificate, the public route must fail before reaching the app:

```bash
curl -i https://conduit-ods.cdnet.uk
```

Expected:

- TLS/client-certificate failure, 403, 400, or equivalent mTLS rejection.
- No Open WebUI, ODS, Ollama, or default proxy page should be visible.

With the phone certificate or a temporary test client certificate:

```bash
curl --cert phone-client.crt --key phone-client.key https://conduit-ods.cdnet.uk
```

Expected:

- Request reaches the intended app/auth layer only after valid client-certificate presentation.
- App auth/API auth is still required where configured.

From Conduit iOS:

- Add an Open WebUI or Direct profile pointing at the mTLS hostname.
- Confirm login/API test succeeds.
- Send one test prompt.
- Confirm streaming works.
- Background and resume the app once during a response if possible.

### Exposure verification

Confirm exposed listeners on the Windows host.

Expected:

- ODS/Open WebUI/Ollama/service containers remain bound to `127.0.0.1` where possible.
- `ods-proxy` is the only intentional LAN-facing ODS HTTP(S) listener.
- The public internet sees only the mTLS reverse-proxy hostname.
- Tailscale Funnel is off.

## Final report required from Freebuff

Return a concise final status containing:

- Actual ODS install path and `.env` path found.
- Values set or intentionally left unset:
  - `BIND_ADDRESS`
  - `ODS_PUBLIC_URL`
  - `ODS_TALK_PUBLIC_URL`
  - `ODS_COOKIE_DOMAIN`
  - `ODS_SERVICE_PUBLIC_URLS`
- `tailscale serve status`.
- LAN DNS/mDNS decision and result.
- Conduit/mTLS hostname, backend target, and certificate issuance/revocation notes.
- Results of the real-device tailnet test.
- Results of the LAN-only device test.
- Results of the no-client-cert and valid-client-cert public mTLS tests.
- Any remaining gaps that prevent calling ODS access complete.

