# Third-party OCPP: running a Njord GO against your own backend

The CTEK Njord GO is a standard **OCPP 1.6J** charge point. Its
`SupportedFeatureProfiles` are `Core, FirmwareManagement, SmartCharging,
RemoteTrigger`, which is everything a generic OCPP central system (CSMS) needs
to fully control it — start/stop, current limiting, schedules, meter values and
remote triggers.

CTEK's cloud exposes an **officially supported** mechanism to point the charger
at a non-CTEK OCPP backend (it's how operators such as Monta or Assemblin
onboard chargers). This document describes that mechanism, as observed from the
cloud API and the Android app, so you can repoint a charger at a self-hosted
CSMS — for example the [`lbbrhzn/ocpp`](https://github.com/lbbrhzn/ocpp)
Home Assistant integration — and control it without the CTEK cloud in the
charging path.

> **Scope / status.** This is reverse-engineered from the public cloud API and
> the shipping app, not from CTEK documentation. Treat it as "works on the
> firmware we tested" (Njord GO, fw `3.2.2`), not a contract. It is independent
> of this Home Assistant integration's normal (cloud) operation.

## TLS: why a self-hosted backend is reachable at all

The charger validates the TLS chain of its OCPP endpoint against a CA bundle
baked into firmware — a naive on-path MITM with an untrusted CA is rejected
(`tlsv1 alert access denied`). However, the curated third-party providers use
ordinary public domains with publicly-trusted certificates over `wss`. So:

- A `wss://` backend on **your own public domain with a normal CA-issued
  certificate** (e.g. Let's Encrypt) is trusted by the charger. No firmware
  changes, no custom CA.
- The app's custom-URL field accepts **both `wss://` and `ws://`** schemes, and
  supports userinfo in the URL (`wss://user:pass@host/...`) for HTTP Basic auth.
  Plain `ws://` is therefore viable on a trusted LAN where you don't want to run
  TLS (at the cost of the OCPP traffic, including any Basic-auth credentials,
  being unencrypted on that LAN).

## The relevant cloud API

All calls are authenticated with the usual `Authorization: Bearer <token>` plus
the standard app headers (`App-Profile`, `User-Agent`, `Timezone`).

### Third-party OCPP

| Operation                    | Method & path                                                 |
| ---------------------------- | ------------------------------------------------------------- |
| List curated providers       | `GET /api/v3/device/thirdparty/ocpp/list?deviceType=NJORD_GO` |
| Read/write charger's backend | `PATCH /api/v3/device/thirdparty/ocpp/{deviceId}`             |

Note the verb is **`PATCH`** (not `POST` — a `POST` returns `405 Method Not
Allowed`). The body is an `OcppSettings` object:

```json
{
  "provider_id": "",
  "raw_url": "ws://<csms-host>:9000/",
  "enabled": true,
  "username": "",
  "password": ""
}
```

- `provider_id` — empty string for a custom URL; otherwise one of the IDs from
  the provider list.
- `raw_url` — the backend base URL. The charge point **appends its own
  `chargeBoxId`** to this base (OCPP-J convention — this is why the curated
  provider domains end in `/`). So a `raw_url` of `ws://host:9000/` results in
  the charger connecting to `ws://host:9000/<chargeBoxId>`.
- `enabled` — `true` to switch to the third-party backend, `false` to revert to
  CTEK cloud.
- `username` / `password` — HTTP Basic credentials, if the backend requires
  them. Leave empty for an unauthenticated CSMS.

The device's current state is reflected in `device/list` under
`device_status.third_party_ocpp_status` (which contains an `enabled` boolean and
the stored settings).

### OCPP configuration key store

The charger's OCPP configuration (standard `GetConfiguration` /
`ChangeConfiguration`) is exposed as:

| Operation     | Method & path                                                                               |
| ------------- | ------------------------------------------------------------------------------------------- |
| Dump all keys | `GET /api/v3/device/configurations?deviceId={deviceId}`                                     |
| Set one key   | `POST /api/v3/device/configuration?deviceId={deviceId}&pushToDevice=true&key={k}&value={v}` |

A write returns `success: true` only once the device **acks** the
`ChangeConfiguration`. Other outcomes:

- `"<Key>: Rejected"` — the firmware refused the value (keys can be effectively
  read-only or value-constrained in firmware even when the cloud reports
  `read_only: false`).
- `"<Key>: Timeout waiting for answer from device"` — the device didn't answer
  in time (transient; rapid-fire writes make this more likely and can briefly
  make a key disappear from the configuration listing until it resyncs).

The OCPP endpoint is also present here as the `Endpoint` key
(`wss://iot.ctek.com/ocpp/` by default); the third-party mechanism above is the
supported way to change it.

## Switching a charger to a self-hosted CSMS

1. Stand up an OCPP 1.6 CSMS reachable by the charger. For
   `lbbrhzn/ocpp`, the central system listens on `:9000` by default and speaks
   subprotocol `ocpp1.6`. Keep it off the public internet (see below).
2. `PATCH /api/v3/device/thirdparty/ocpp/{deviceId}` with `enabled: true` and
   your `raw_url`.
3. Optionally send an OCPP `REBOOT` (`POST /api/v3/device/control` with
   `{"device_id": "...", "instruction": "REBOOT"}`) to force an immediate
   reconnect rather than waiting for the charger's own reconnect cycle.
4. Watch the CSMS log for the incoming WebSocket connection — the path segment
   is the `chargeBoxId`. Register that ID in your CSMS so it binds entities.

Once the charger has repointed its OCPP channel to your CSMS, the CTEK cloud can
no longer deliver OCPP commands to it (e.g. a cloud `REBOOT` will time out) —
that's expected, and is itself a sign the switch took effect.

### Reverting

`PATCH … {"enabled": false}` returns the charger to the CTEK cloud backend.

## Keeping the CSMS off the internet

The charger reaches the CSMS over the LAN, so the OCPP port does not need to be
internet-exposed. Recommended:

- Bind the CSMS to the LAN address, not `0.0.0.0`.
- Add **no** WAN port-forward / DNAT for the OCPP port, and keep the router's WAN
  input policy at drop/reject (the default).
- If you need `wss://` on a public hostname, terminate TLS on a **dedicated**
  reverse-proxy frontend bound to the LAN address on a non-forwarded port — do
  not place the OCPP endpoint on a frontend that is reachable from the internet
  (e.g. a shared public `:443` with SNI routing). Use split-horizon DNS so the
  hostname resolves to the LAN address internally.
- Set a CSMS username/password (and matching `username`/`password` in the
  `OcppSettings` body), since an open CSMS will accept any charge point.

## Reconnect behaviour after a network outage

The WebSocket reconnect backoff is governed by these configuration keys:

| Key                       | Meaning                            |
| ------------------------- | ---------------------------------- |
| `RetryBackOffWaitMinimum` | first retry delay (s)              |
| `RetryBackOffWaitMaximum` | ceiling on the backoff (s)         |
| `RetryBackOffRandomRange` | random jitter added (s)            |
| `RetryBackOffRepeatTimes` | number of doublings before capping |

The default `RetryBackOffWaitMaximum` is `18000` (5 hours), which means that
after a long outage the charger can sit in a multi-hour backoff and appear to
"never reconnect" well after the network is back. Lowering the ceiling helps.
Note the firmware **rejects values that are too low** (e.g. `300` is rejected);
values around `1800` (30 min) are accepted. These keys also govern reconnection
to a third-party backend.
