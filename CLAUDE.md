# CLAUDE.md — ha-ctek

Home Assistant custom integration for CTEK EV chargers. Communicates with the CTEK cloud API over HTTPS and WebSocket (`cloud_push` iot_class).

## Branching strategy

- `dev` — integration development, base branch for feature PRs
- `main` — stable/release branch, merged from `dev`
- Feature branches should be cut from `dev` and target `dev` in PRs

## Release flow

Versions follow `x.y.z` semver. Pre-releases use suffixes: `0.0.11-alpha1`, `0.0.11-beta1`, `0.0.11-rc1`, then `0.0.11`.

HACS users on the **experimental channel** receive pre-releases. Stable channel users only receive full releases.

### Working on the next release

While developing, accumulate human-readable entries under a single `## [<next-version>] - unreleased` section at the top of `CHANGELOG.md`. Dependency-only bumps don't need their own bullets — they're aggregated automatically by the release script (see below).

### Publishing a release (pre-release or stable)

`bump_version.sh` is the **single source of truth** for version bumps. Do **not** edit `manifest.json`, `const.py`, or the unreleased CHANGELOG header by hand — let the script do it so the format stays consistent and the dependency aggregation runs.

The script:

- syncs with upstream via `git pull --rebase` so freshly merged PRs are visible to the dep-bump scan (skipped automatically if no upstream is configured; opt out with `BUMP_NO_PULL=1`),
- updates the version string in `custom_components/ctek/manifest.json` and `custom_components/ctek/const.py`,
- date-stamps the existing `## [<x.y.z>] - unreleased` section to `## [<new-version>] - YYYY-MM-DD`,
- scans `chore(deps): bump …` commits since the last git tag and adds a single `- Update dependencies (pkg1, pkg2, …)` line under `### Changed` (creating the block if absent), deduplicated,
- stages the modified files (does **not** commit — review first).

Steps:

1. Make sure all PRs are merged into `dev` and CI is green. For a **stable** release, first merge `dev` into `main` via PR and run the rest from `main`.
2. Run the script with the target version:

   ```bash
   bash bump_version.sh 0.0.11-beta1   # pre-release
   # or
   bash bump_version.sh 0.0.11         # stable
   ```

3. Review the diff (`git diff --staged`). Tidy any rough edges in the dated CHANGELOG section.
4. Commit and push:

   ```bash
   git commit -m "Bump version to 0.0.11-beta1"
   git pull --rebase && git push
   ```

5. Create the GitHub release. For pre-releases pass `--prerelease`; for stable, omit it. The `awk` extracts only the freshly dated section's body:

   ```bash
   VER=0.0.11-beta1
   NOTES=$(awk -v v="$VER" '$0=="## ["v"] - "strftime("%Y-%m-%d"){flag=1;next} /^## \[/{flag=0} flag' CHANGELOG.md)
   gh release create "$VER" --prerelease --title "$VER" --target dev --notes "$NOTES"
   ```

   (For stable releases drop `--prerelease`, set `--target main`, and the version like `VER=0.0.11`.)

6. Start the next cycle by adding a fresh `## [<next-version>] - unreleased` block at the top of `CHANGELOG.md`. **Always commit this on `dev`** (never on `main`) — it can be its own commit or piggy-back on the next change. After a stable release cut from `main`, switch back to `dev` first; once `main` is merged back, add the new unreleased section there.

### Tests

The script has integration tests in `tests/test_bump_version.py`. Run them after any change to `bump_version.sh`:

```bash
pytest tests/test_bump_version.py
```

## Before pushing any changes

Run pre-commit hooks (covers ruff, codespell, yamllint, pymarkdown, mypy, prettier, etc.):

```bash
source venv/bin/activate
pre-commit run --all-files
```

Then run tests with coverage:

```bash
pytest --cov=./custom_components/ --cov-config=.coveragerc --cov-report=term-missing
```

Fix any lint or format issues before committing. New code should be covered by tests — check the `Missing` column in the coverage report for uncovered lines in changed files.

## Local setup

Requires **Python 3.14+** (CI uses 3.14).

```bash
python3.14 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pre-commit install
```

## Pre-commit hooks

Most hooks use `language: system` and run tools from the local venv (defined in `requirements.txt`). Generic file hygiene hooks use `pre-commit/pre-commit-hooks`. Only `prettier` uses a remote Node.js repo.

| Hook                | Tool                        | Source                      |
| ------------------- | --------------------------- | --------------------------- |
| ruff                | `ruff check --fix`          | local (requirements.txt)    |
| ruff-format         | `ruff format`               | local                       |
| codespell           | `codespell`                 | local                       |
| yamllint            | `yamllint`                  | local                       |
| pymarkdown          | `pymarkdown scan`           | local                       |
| mypy                | `mypy` (config in mypy.ini) | local                       |
| check-json          | JSON syntax check           | pre-commit/pre-commit-hooks |
| no-commit-to-branch | blocks commits to `main`    | pre-commit/pre-commit-hooks |
| end-of-file-fixer   | ensures trailing newline    | pre-commit/pre-commit-hooks |
| trailing-whitespace | removes trailing whitespace | pre-commit/pre-commit-hooks |
| prettier            | `prettier`                  | mirrors-prettier            |

Manual-only hooks (run with `pre-commit run --hook-stage manual`):

- `check-executables-have-shebangs` (pre-commit/pre-commit-hooks)
- `python-typing-update` (local)

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

Workflow files are in `.github/workflows/`. Each job has an explicit `permissions` block (required by CodeQL).

| Workflow          | Job        | What it does                                           |
| ----------------- | ---------- | ------------------------------------------------------ |
| `test.yml`        | `setup`    | Install deps, cache venv                               |
| `test.yml`        | `lint`     | `ruff check`, `ruff format --check`, `pymarkdown scan` |
| `test.yml`        | `tests`    | `pytest` + coverage comment on PR                      |
| `validate.yml`    | `hassfest` | Home Assistant integration validation                  |
| `validate.yml`    | `hacs`     | HACS store validation                                  |
| `coverage.yml`    | —          | Posts coverage comment from artifact                   |
| `osv-scanner.yml` | —          | OSV vulnerability scanning                             |
