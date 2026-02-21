# CLAUDE.md — ha-ctek

Home Assistant custom integration for CTEK EV chargers. Communicates with the CTEK cloud API over HTTPS and WebSocket (`cloud_push` iot_class).

## Branching strategy

- `dev` — integration development, base branch for feature PRs
- `main` — stable/release branch, merged from `dev`
- Feature branches should be cut from `dev` and target `dev` in PRs

## Release flow

Versions follow `x.y.z` semver. Pre-releases use suffixes: `0.0.11-alpha1`, `0.0.11-beta1`, then `0.0.11`.

HACS users on the **experimental channel** receive pre-releases. Stable channel users only receive full releases.

### Publishing a pre-release (development version)

1. Make sure all PRs are merged into `dev` and CI is green.
2. Update `CHANGELOG.md` — ensure the upcoming version section has clear, human-readable entries covering all changes since the **last non-pre-release** version. Dependency-only bumps can be grouped as "Update dependencies".
3. Update the version in `manifest.json` and `const.py` manually (the bump script does not support pre-release suffixes):

   ```bash
   sed -i 's/"version": ".*"/"version": "0.0.11-alpha1"/' custom_components/ctek/manifest.json
   sed -i 's/VERSION = ".*"/VERSION = "0.0.11-alpha1"/' custom_components/ctek/const.py
   ```

4. Review and tidy `CHANGELOG.md` (the script adds placeholder entries).
5. Commit and push to `dev`:

   ```bash
   git add manifest.json custom_components/ctek/const.py CHANGELOG.md
   git commit -m "Bump version to 0.0.11-alpha1"
   git push
   ```

6. Create a GitHub **pre-release** with the matching tag:

   ```bash
   gh release create 0.0.11-alpha1 --prerelease --title "0.0.11-alpha1" \
     --notes "$(sed -n '/## \[0.0.11\]/,/## \[0.0.10\]/{ /## \[0.0.10\]/!p }' CHANGELOG.md | sed '1d')"
   ```

### Publishing a stable release

1. Merge `dev` into `main` via PR — do not push directly to `main`.
2. On `main`, run the version bump script (without pre-release suffix):

   ```bash
   bash bump_version.sh 0.0.11
   ```

3. Update `CHANGELOG.md` — the entry should cover all changes since the **last stable release** (`0.0.10`), not just since the last alpha/beta.
4. Commit, push, and create a **full release** (not pre-release):

   ```bash
   gh release create 0.0.11 --title "0.0.11" \
     --notes "$(sed -n '/## \[0.0.11\]/,/## \[0.0.10\]/{ /## \[0.0.10\]/!p }' CHANGELOG.md | sed '1d')"
   ```

## Before pushing any changes

Always run the following in order:

```bash
# 1. Lint (ruff)
.venv/bin/python -m ruff check .

# 2. Format check (ruff)
.venv/bin/python -m ruff format . --check

# 3. Markdown lint
.venv/bin/pymarkdown scan **/*.md

# 4. Tests with coverage
.venv/bin/pytest --cov=./custom_components/ --cov-config=.coveragerc --cov-report=term-missing
```

Fix any lint or format issues before committing. New code should be covered by tests — check the `Missing` column in the coverage report for uncovered lines in changed files.

## Local setup

Requires **Python 3.13** (CI uses 3.13; versions ≥3.13 are required by `pytest-homeassistant-custom-component`).

```bash
# Install Python 3.13 via Homebrew if not available
brew install python@3.13

# Create venv and install dependencies
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

> **Note:** pin `pycares<5` is no longer needed as of `homeassistant>=2026.2.x` (aiodns 4.0.0 requires pycares>=5). If tests fail at startup with `AttributeError: module 'pycares' has no attribute 'ares_query_a_result'`, downgrade pycares: `.venv/bin/pip install "pycares<5"`.

## Project layout

```text
custom_components/ctek/
  __init__.py          # Integration setup/teardown, entry point
  api.py               # HTTP API client (auth, token refresh, commands)
  coordinator.py       # DataUpdateCoordinator: polling, WS management, charge logic
  ws.py                # WebSocket client for real-time device updates
  config_flow.py       # HA config flow (UI setup/reconfiguration)
  data.py              # TypedDicts for runtime data structures
  parser.py            # Parse API/WS responses into internal data types
  enums.py             # ChargeStateEnum and other domain enums
  const.py             # Constants, URLs, custom exception classes
  entity.py            # Base entity class
  sensor.py            # Sensor entities
  binary_sensor.py     # Binary sensor entities
  switch.py            # Switch entities (start/stop charge)
  number.py            # Number entities (current limit etc.)
  services.yaml        # HA service definitions
  strings.json         # UI strings
  translations/        # Localisation files

tests/
  conftest.py
  test_api.py          # CtekApiClient unit tests (auth, token refresh)
  test_binary_sensor.py
  test_config_flow.py
  test_entity.py
  test_number.py
  test_parser.py
```

## Key architecture notes

### Authentication

- OAuth2 password grant + refresh token flow against `https://iot.ctek.com/oauth/token`
- `CtekApiClient.refresh_access_token()` tries the refresh token first, falls back to password login if the refresh token is rejected (401)
- Token refresh is triggered automatically inside `_api_wrapper` on a 401 response; only applies to authenticated requests (`auth=True`)
- After a token refresh the updated `Authorization` header is injected before the retry request
- `CtekApiClientAuthenticationError` is never swallowed — it propagates through the broad `except Exception` handler explicitly so callers can distinguish auth failures from generic errors

### Exception hierarchy

```text
CtekApiClientError
  CtekApiClientCommunicationError  # network / timeout
  CtekApiClientAuthenticationError # 401 / bad credentials
```

The coordinator converts `CtekApiClientAuthenticationError` → `ConfigEntryAuthFailed` (triggers HA re-auth notification) during polling. Service calls (send_command, start/stop charge) do not currently trigger re-auth automatically — see issue #156.

### Coordinator

- Extends `TimestampDataUpdateCoordinator`
- Handles periodic REST polling + WebSocket subscription for real-time updates
- WebSocket is restarted at most once every 5 minutes unless forced
- `handle_car_quirks` implements retry logic for stubborn chargers (max 3 attempts, 60 s apart by default)

### Services

- `force_refresh` — trigger an immediate data refresh
- `send_command` — send an arbitrary OCPP instruction to the charger (e.g. `REBOOT`)

## CI checks (GitHub Actions)

| Check | Tool |
|---|---|
| Lint | `ruff check` |
| Format | `ruff format --check` |
| Markdown lint | `pymarkdown scan` |
| Tests | `pytest` + coverage report posted to PR |
| HA validation | Hassfest |
| HACS validation | HACS action |
| Security scan | OSV Scanner, CodeQL |
