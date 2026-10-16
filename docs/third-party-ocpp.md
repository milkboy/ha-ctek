# Third-party OCPP: running a Njord GO against your own backend

The CTEK Njord GO is a standard **OCPP 1.6J** charge point. Its
`SupportedFeatureProfiles` are `Core, FirmwareManagement, SmartCharging,
RemoteTrigger`, which is everything a generic OCPP central system (CSMS) needs
to fully control it — start/stop, current limiting, schedules, meter values and
remote triggers.

CTEK's cloud has a third-party-OCPP feature (it's how operators such as Monta or
Assemblin onboard chargers). This document describes how to use it — plus the
lower-level `Endpoint` config key — to repoint a charger at a self-hosted CSMS,
for example the [`lbbrhzn/ocpp`](https://github.com/lbbrhzn/ocpp) Home Assistant
integration, and control it without the CTEK cloud in the charging path.

> **Scope / status.** Reverse-engineered from the public cloud API and the
> shipping app, not from CTEK documentation. Confirmed working on a Njord GO
> (fw `3.2.2`), but treat it as "worked for us," not a contract. It is
> independent of this integration's normal (cloud) operation.

## TLS: why a self-hosted backend is reachable at all

The charger validates the TLS chain of its OCPP endpoint against a CA bundle
baked into firmware — a naive on-path MITM with an untrusted CA is rejected
(`tlsv1 alert access denied`). But the curated third-party providers use ordinary
public domains with publicly-trusted certs over `wss` (one, `chargepanel.com`,
uses Let's Encrypt), so the firmware trusts the normal public CA set. Therefore:

- A **`wss://` endpoint on your own domain with a normal CA-issued cert** (e.g.
  Let's Encrypt) is trusted by the charger — no firmware changes, no custom CA.
- **Plaintext `ws://` does _not_ work.** The app's custom-URL field validates
  both `ws://` and `wss://` strings, but the firmware we tested never actually
  opened a plaintext OCPP connection — it silently stayed on its CTEK `wss`
  endpoint. Use `wss://`. (The URL may carry userinfo —
  `wss://user:pass@host/…` — for HTTP Basic auth to your CSMS.)

So the endpoint must be `wss`, which means terminating TLS somewhere the charger
can reach (see [Keeping the CSMS off the internet](#keeping-the-csms-off-the-internet)).

## The relevant cloud API

All calls are authenticated with `Authorization: Bearer <token>` plus the
standard app headers (`App-Profile`, `User-Agent`, `Timezone`).

### Third-party OCPP

| Operation                    | Method & path                                                 |
| ---------------------------- | ------------------------------------------------------------- |
| List curated providers       | `GET /api/v3/device/thirdparty/ocpp/list?deviceType=NJORD_GO` |
| Read/write charger's backend | `PATCH /api/v3/device/thirdparty/ocpp/{deviceId}`             |

The verb is **`PATCH`** (`POST` → `405 Method Not Allowed`). Body is an
`OcppSettings` object:

```json
{
  "provider_id": "",
  "raw_url": "wss://<csms-host>:<port>/",
  "enabled": true,
  "username": "",
  "password": ""
}
```

- `provider_id` — empty for a custom URL; otherwise an ID from the provider list.
- `raw_url` — the backend **base** URL. The charge point **appends its own
  `chargeBoxId`** (OCPP-J convention — which is why the curated provider domains
  end in `/`). For the Njord GO the `chargeBoxId` equals the **`device_id`**, so
  a `raw_url` of `wss://host:9443/` yields `wss://host:9443/<device_id>`.
- `enabled` — see the recipe below; on its own this flag did **not** propagate
  the endpoint to the device on our account (the in-app UI for this feature was
  also absent, i.e. it appears gated server-side). Its observable effect is that
  it makes CTEK **stop reasserting** the `Endpoint` key (next section).
- `username` / `password` — HTTP Basic credentials for your CSMS, if required.

Current state is reflected in `device/list` under
`device_status.third_party_ocpp_status` (an `enabled` boolean plus the stored
settings).

### OCPP configuration key store

Standard `GetConfiguration` / `ChangeConfiguration`, exposed as:

| Operation     | Method & path                                                                               |
| ------------- | ------------------------------------------------------------------------------------------- |
| Dump all keys | `GET /api/v3/device/configurations?deviceId={deviceId}`                                     |
| Set one key   | `POST /api/v3/device/configuration?deviceId={deviceId}&pushToDevice=true&key={k}&value={v}` |

A write returns `success: true` only once the device **acks** the
`ChangeConfiguration`. Other outcomes:

- `"<Key>: Rejected"` — firmware refused the value (keys can be effectively
  read-only or value-constrained even when the cloud reports `read_only: false`).
- `"<Key>: Timeout waiting for answer from device"` — the device didn't answer
  in time (more likely on a flaky link or under rapid-fire writes; a key can
  briefly vanish from the listing until it resyncs).

The OCPP backend URL lives here as the **`Endpoint`** key
(`wss://iot.ctek.com/ocpp/` by default).

## Switching a charger to a self-hosted CSMS — the recipe that sticks

Neither lever alone was enough on our account:

- **`Endpoint` key alone doesn't stick.** Writing it (`key=Endpoint`,
  `value=<wss>`) is accepted and triggers an _immediate_ reconnect to the new
  URL. But if that session fails, the charger falls back to CTEK and **CTEK
  re-pushes its own `Endpoint`**, undoing the change.
- **Third-party `enabled:true` alone doesn't repoint the device** (endpoint not
  propagated — feature gated), but it makes CTEK **stand down** and stop
  reasserting `Endpoint`.

**Set both, in this order:**

1. **Register the charge point in your CSMS first**, with CPID = the charger's
   `chargeBoxId` (= `device_id`). If the CSMS drops an unknown CP, the very first
   session closes in ~100 ms → the charger falls back to CTEK → CTEK reasserts,
   and you're back to square one.
2. `PATCH /api/v3/device/thirdparty/ocpp/{deviceId}` with `enabled: true` and
   `raw_url` = your `wss` base. (CTEK now stops reasserting.)
3. `set_config Endpoint = <same wss base>`. This write triggers the charger's
   immediate reconnect to your CSMS; because the CP is registered the session
   **holds**, and because the third-party flag is on, CTEK doesn't claw the
   endpoint back. The charger stays put.

A cloud `REBOOT` (`POST /api/v3/device/control`,
`{"device_id":"…","instruction":"REBOOT"}`) can force a clean reconnect **while
the charger is still reachable on CTEK**. Once it has moved to your CSMS, cloud
commands time out (`error_code 931`) — expected, and itself a sign the switch
took. From then on, send config/resets via your own CSMS (e.g. `lbbrhzn/ocpp`'s
`ocpp.configure` / reset services).

### Reverting

- **Bluetooth (the app), locally** — reliably disables third-party OCPP even when
  the charger is off the cloud. This is the dependable recovery path if a switch
  ever strands the charger.
- `PATCH … {"enabled": false}` clears the cloud flag; CTEK then reasserts its own
  `Endpoint` the next time the charger is on its channel.

## Keeping the CSMS off the internet

The charger reaches the CSMS over the LAN, so the OCPP port need not be
internet-exposed. Because the endpoint must be `wss`, terminate TLS on a
dedicated proxy and keep it LAN-only:

- Terminate `wss` on a **dedicated** reverse-proxy frontend bound to the LAN
  address on a **non-forwarded** port (e.g. haproxy `bind 10.0.0.x:9443 ssl crt
…`, `mode http`, `timeout tunnel 24h`, backend → the CSMS's plain-`ws` port).
  Do **not** place it on a frontend reachable from the internet (e.g. a shared
  public `:443` with SNI routing).
- Pin the frontend to HTTP/1.1 (`alpn http/1.1`) so a client can't negotiate
  HTTP/2, which breaks the WebSocket `Upgrade`.
- Use **split-horizon DNS** so the endpoint hostname resolves to the LAN proxy
  internally; keep no WAN DNAT for the port and the router's WAN input at
  drop/reject. The cert hostname must match the `raw_url`/`Endpoint` host (the
  charger validates by hostname; a bare IP won't match a DNS-only SAN).
- Issuing a public cert publishes the hostname to Certificate Transparency logs,
  so expect immediate `/.env`-style scans on any _forwarded_ port for that name —
  harmless if the OCPP port isn't forwarded, but worth having an IPS/ban in place.
- Set a CSMS username/password (and matching `username`/`password` in the
  `OcppSettings`, or userinfo in the URL) — an open CSMS accepts any charge point.

## Reconnect behaviour after a network outage

The WebSocket reconnect backoff is governed by these configuration keys:

| Key                       | Meaning                            |
| ------------------------- | ---------------------------------- |
| `RetryBackOffWaitMinimum` | first retry delay (s)              |
| `RetryBackOffWaitMaximum` | ceiling on the backoff (s)         |
| `RetryBackOffRandomRange` | random jitter added (s)            |
| `RetryBackOffRepeatTimes` | number of doublings before capping |

The default `RetryBackOffWaitMaximum` is `18000` (5 hours), so after a long
outage the charger can sit in a multi-hour backoff and appear to "never
reconnect" well after the network is back. Lowering the ceiling helps, but the
firmware **rejects values that are too low** (`300` was rejected; `1800` was
accepted). These keys govern reconnection to a third-party backend too.

## What populates in Home Assistant

`lbbrhzn/ocpp` exposes a superset of entities; the charger only fills the
measurands it actually reports. The Njord GO's `MeterValuesSampledData` defaults
to `Energy.Active.Import.Register, Current.Import, Power.Active.Import`, so
energy/current/power populate and the rest stay "unknown". Add measurands the
firmware supports (e.g. `Voltage`) via `ChangeConfiguration` on
`MeterValuesSampledData` to get more — sent through your CSMS once the charger
has switched over.
