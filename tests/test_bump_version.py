"""Integration tests for bump_version.sh.

Each test sets up a fresh temp git repo with just the files the script
touches, runs the script as a subprocess, and asserts on the resulting
file contents and exit code.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "bump_version.sh"

MANIFEST_REL = "custom_components/ctek/manifest.json"
CONST_REL = "custom_components/ctek/const.py"
CHANGELOG_REL = "CHANGELOG.md"

INITIAL_MANIFEST = '{\n  "version": "0.0.10"\n}\n'
INITIAL_CONST = 'VERSION = "0.0.10"\n'
INITIAL_CHANGELOG_TEMPLATE = """\
# Changelog

## [0.0.11] - unreleased

### Fixed

- Some user-facing fix
{extra}
## [0.0.10] - 2025-09-15

### Fixed

- Older fix
"""


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        },
    )


def _run_script(
    cwd: Path,
    version: str,
    *,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(cwd / "bump_version.sh"), version],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A temp git repo with the project layout the script expects."""
    (tmp_path / "custom_components" / "ctek").mkdir(parents=True)
    (tmp_path / MANIFEST_REL).write_text(INITIAL_MANIFEST)
    (tmp_path / CONST_REL).write_text(INITIAL_CONST)
    (tmp_path / CHANGELOG_REL).write_text(INITIAL_CHANGELOG_TEMPLATE.format(extra=""))
    shutil.copy(SCRIPT, tmp_path / "bump_version.sh")
    (tmp_path / "bump_version.sh").chmod(0o755)

    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "initial")
    _git(tmp_path, "tag", "0.0.10")
    return tmp_path


def _add_commit(repo: Path, subject: str) -> None:
    """Add an empty commit with the given subject (for git log scanning)."""
    _git(repo, "commit", "-q", "--allow-empty", "-m", subject)


def _today() -> str:
    # Match the script's `date +%Y-%m-%d`, which uses the local clock.
    return datetime.now().astimezone().strftime("%Y-%m-%d")


# ---- happy paths ------------------------------------------------------------


def test_stable_version_updates_manifest_const_and_changelog(repo: Path):
    result = _run_script(repo, "0.0.11")

    assert result.returncode == 0, result.stderr
    assert '"version": "0.0.11"' in (repo / MANIFEST_REL).read_text()
    assert 'VERSION = "0.0.11"' in (repo / CONST_REL).read_text()
    changelog = (repo / CHANGELOG_REL).read_text()
    assert f"## [0.0.11] - {_today()}" in changelog
    assert "## [0.0.11] - unreleased" not in changelog


@pytest.mark.parametrize(
    "version", ["0.0.11-alpha1", "0.0.11-beta2", "0.0.11-rc1", "1.2.3-alpha10"]
)
def test_prerelease_versions_accepted(repo: Path, version: str):
    result = _run_script(repo, version)
    assert result.returncode == 0, result.stderr
    assert f'"version": "{version}"' in (repo / MANIFEST_REL).read_text()
    assert f'VERSION = "{version}"' in (repo / CONST_REL).read_text()
    assert f"## [{version}] - {_today()}" in (repo / CHANGELOG_REL).read_text()


# ---- invalid input ----------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    ["", "0.0", "v0.0.11", "0.0.11-pre", "0.0.11-alpha", "0.0.11.1", "abc"],
)
def test_invalid_version_format_rejected(repo: Path, bad: str):
    result = _run_script(repo, bad)
    assert result.returncode != 0
    # Files must be untouched.
    assert (repo / MANIFEST_REL).read_text() == INITIAL_MANIFEST
    assert (repo / CONST_REL).read_text() == INITIAL_CONST


def test_missing_unreleased_section_errors(repo: Path):
    (repo / CHANGELOG_REL).write_text(
        "# Changelog\n\n## [0.0.10] - 2025-09-15\n\n- previous\n"
    )
    _git(repo, "commit", "-q", "-am", "drop unreleased")

    result = _run_script(repo, "0.0.11")

    assert result.returncode != 0
    assert "unreleased" in result.stderr.lower()


def test_dirty_working_tree_outside_managed_files_rejected(repo: Path):
    (repo / "stray.txt").write_text("oops")

    result = _run_script(repo, "0.0.11")

    assert result.returncode != 0
    assert "uncommitted" in result.stderr.lower()


def test_dirty_managed_files_allowed(repo: Path):
    """Modifications to manifest/const/CHANGELOG before run are fine — the
    script is going to rewrite them anyway."""
    (repo / MANIFEST_REL).write_text('{\n  "version": "0.0.10-dev"\n}\n')

    result = _run_script(repo, "0.0.11")

    assert result.returncode == 0, result.stderr


# ---- dependency-bump aggregation -------------------------------------------


def test_dep_bumps_inserted_under_existing_changed_block(repo: Path):
    (repo / CHANGELOG_REL).write_text(
        INITIAL_CHANGELOG_TEMPLATE.format(
            extra="\n### Changed\n\n- Existing changed entry\n"
        )
    )
    _git(repo, "commit", "-q", "-am", "add Changed block")
    _add_commit(repo, "chore(deps): bump ruff from 0.15.11 to 0.15.12")
    _add_commit(repo, "chore(deps): bump pytest from 8.0.0 to 8.1.0")

    result = _run_script(repo, "0.0.11-beta3")

    assert result.returncode == 0, result.stderr
    changelog = (repo / CHANGELOG_REL).read_text()
    # Single line covering both packages, in commit order.
    assert "- Update dependencies (ruff, pytest)" in changelog
    # Existing entry preserved.
    assert "- Existing changed entry" in changelog


def test_dep_bumps_create_changed_block_when_missing(repo: Path):
    _add_commit(repo, "chore(deps): bump aiohttp from 3.10.0 to 3.10.1")

    result = _run_script(repo, "0.0.11-beta3")

    assert result.returncode == 0, result.stderr
    changelog = (repo / CHANGELOG_REL).read_text()
    # Locate the new section.
    section_re = re.compile(
        r"^## \[0\.0\.11-beta3\] - \d{4}-\d{2}-\d{2}$"
        r".*?(?=^## \[)",
        re.DOTALL | re.MULTILINE,
    )
    match = section_re.search(changelog)
    assert match, "new section not found"
    section = match.group(0)
    assert "### Changed" in section
    assert "- Update dependencies (aiohttp)" in section


def test_dep_bumps_deduplicate_packages(repo: Path):
    _add_commit(repo, "chore(deps): bump ruff from 0.15.10 to 0.15.11")
    _add_commit(repo, "chore(deps): bump ruff from 0.15.11 to 0.15.12")
    _add_commit(repo, "chore(deps): bump aiohttp from 3.10.0 to 3.10.1")

    result = _run_script(repo, "0.0.11-beta3")

    assert result.returncode == 0, result.stderr
    changelog = (repo / CHANGELOG_REL).read_text()
    # ruff appears once, not twice.
    deps_lines = [
        line for line in changelog.splitlines() if "Update dependencies" in line
    ]
    assert len(deps_lines) == 1
    assert deps_lines[0] == "- Update dependencies (ruff, aiohttp)"


def test_existing_deps_line_not_duplicated(repo: Path):
    (repo / CHANGELOG_REL).write_text(
        INITIAL_CHANGELOG_TEMPLATE.format(
            extra="\n### Changed\n\n- Update dependencies (manual entry)\n"
        )
    )
    _git(repo, "commit", "-q", "-am", "manual deps")
    _add_commit(repo, "chore(deps): bump ruff from 0.15.11 to 0.15.12")

    result = _run_script(repo, "0.0.11-beta3")

    assert result.returncode == 0, result.stderr
    changelog = (repo / CHANGELOG_REL).read_text()
    deps_lines = [
        line for line in changelog.splitlines() if "Update dependencies" in line
    ]
    assert len(deps_lines) == 1
    assert "manual entry" in deps_lines[0]


def test_no_dep_bumps_no_changed_block_added(repo: Path):
    """When there are no chore(deps) commits, the script must not invent
    a Changed block."""
    _add_commit(repo, "fix: something user-facing")

    result = _run_script(repo, "0.0.11-beta3")

    assert result.returncode == 0, result.stderr
    changelog = (repo / CHANGELOG_REL).read_text()
    section_re = re.compile(
        r"^## \[0\.0\.11-beta3\] - \d{4}-\d{2}-\d{2}$"
        r".*?(?=^## \[)",
        re.DOTALL | re.MULTILINE,
    )
    match = section_re.search(changelog)
    assert match is not None
    assert "### Changed" not in match.group(0)


def test_dep_bumps_handle_update_requirement_subject(repo: Path):
    """Dependabot uses 'update <pkg> requirement' for pip constraints in
    addition to 'bump <pkg>' for libraries. Both must be aggregated."""
    _add_commit(repo, "chore(deps): bump aiohttp from 3.10.0 to 3.10.1")
    _add_commit(repo, "chore(deps): update pip requirement from >=26.1 to >=26.1.1")

    result = _run_script(repo, "0.0.11-rc2")

    assert result.returncode == 0, result.stderr
    changelog = (repo / CHANGELOG_REL).read_text()
    deps = [line for line in changelog.splitlines() if "Update dependencies" in line]
    assert len(deps) == 1
    assert "aiohttp" in deps[0]
    assert "pip" in deps[0]


def test_dep_bumps_handle_grouped_deps_subject(repo: Path):
    """Dependabot grouped/scoped subjects like
    'chore(deps-dev): bump pkg' should still be parsed."""
    _add_commit(repo, "chore(deps-dev): bump mypy from 1.20.1 to 1.20.2")
    _add_commit(repo, "chore(deps): bump py-cov-action/python-coverage-comment-action")

    result = _run_script(repo, "0.0.11-beta3")

    assert result.returncode == 0, result.stderr
    changelog = (repo / CHANGELOG_REL).read_text()
    deps = [line for line in changelog.splitlines() if "Update dependencies" in line]
    assert len(deps) == 1
    assert "mypy" in deps[0]
    assert "py-cov-action/python-coverage-comment-action" in deps[0]


# ---- upstream sync ----------------------------------------------------------


def test_no_upstream_runs_without_pull(repo: Path):
    """The default repo fixture has no remote; the script must still succeed."""
    result = _run_script(repo, "0.0.11-rc1")
    assert result.returncode == 0, result.stderr
    assert "(sync with upstream)" not in result.stdout


def test_pull_picks_up_merged_dep_bump_from_remote(tmp_path: Path):
    """A dep bump merged on the upstream branch but not yet pulled locally
    must still appear in the aggregated 'Update dependencies' line."""
    # Set up: bare remote, local clone, original commit pushed.
    bare = tmp_path / "remote.git"
    _git(tmp_path, "init", "--bare", "-q", "-b", "main", str(bare))

    work = tmp_path / "work"
    work.mkdir()
    (work / "custom_components" / "ctek").mkdir(parents=True)
    (work / MANIFEST_REL).write_text(INITIAL_MANIFEST)
    (work / CONST_REL).write_text(INITIAL_CONST)
    (work / CHANGELOG_REL).write_text(INITIAL_CHANGELOG_TEMPLATE.format(extra=""))
    shutil.copy(SCRIPT, work / "bump_version.sh")
    (work / "bump_version.sh").chmod(0o755)
    _git(work, "init", "-q", "-b", "main")
    _git(work, "remote", "add", "origin", str(bare))
    _git(work, "add", ".")
    _git(work, "commit", "-q", "-m", "initial")
    _git(work, "tag", "0.0.10")
    _git(work, "push", "-q", "-u", "origin", "main")
    _git(work, "push", "-q", "--tags")

    # Add a dep-bump commit on a separate clone and push to the remote, so the
    # local `work` clone is now behind by one commit.
    other = tmp_path / "other"
    _git(tmp_path, "clone", "-q", str(bare), str(other))
    _git(
        other,
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "chore(deps): bump aiohttp from 3.10.0 to 3.10.1",
    )
    _git(other, "push", "-q", "origin", "main")

    # The local clone hasn't pulled yet — confirm the bump isn't visible locally.
    local_log = _git(work, "log", "--oneline").stdout
    assert "aiohttp" not in local_log

    result = _run_script(work, "0.0.11-rc1")

    assert result.returncode == 0, result.stderr
    assert "(sync with upstream)" in result.stdout
    changelog = (work / CHANGELOG_REL).read_text()
    assert "- Update dependencies (aiohttp)" in changelog


def test_bump_no_pull_env_var_skips_pull(tmp_path: Path):
    """Setting BUMP_NO_PULL=1 must skip the upstream sync even when an
    upstream is configured."""
    bare = tmp_path / "remote.git"
    _git(tmp_path, "init", "--bare", "-q", "-b", "main", str(bare))

    work = tmp_path / "work"
    work.mkdir()
    (work / "custom_components" / "ctek").mkdir(parents=True)
    (work / MANIFEST_REL).write_text(INITIAL_MANIFEST)
    (work / CONST_REL).write_text(INITIAL_CONST)
    (work / CHANGELOG_REL).write_text(INITIAL_CHANGELOG_TEMPLATE.format(extra=""))
    shutil.copy(SCRIPT, work / "bump_version.sh")
    (work / "bump_version.sh").chmod(0o755)
    _git(work, "init", "-q", "-b", "main")
    _git(work, "remote", "add", "origin", str(bare))
    _git(work, "add", ".")
    _git(work, "commit", "-q", "-m", "initial")
    _git(work, "tag", "0.0.10")
    _git(work, "push", "-q", "-u", "origin", "main")

    result = _run_script(work, "0.0.11-rc1", extra_env={"BUMP_NO_PULL": "1"})

    assert result.returncode == 0, result.stderr
    assert "(sync with upstream)" not in result.stdout


# ---- staging behavior -------------------------------------------------------


def test_modified_files_are_staged(repo: Path):
    result = _run_script(repo, "0.0.11-beta3")
    assert result.returncode == 0, result.stderr

    staged = _git(repo, "diff", "--name-only", "--cached").stdout.split()
    assert MANIFEST_REL in staged
    assert CONST_REL in staged
    assert CHANGELOG_REL in staged


def test_script_does_not_create_commit(repo: Path):
    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    result = _run_script(repo, "0.0.11-beta3")
    assert result.returncode == 0, result.stderr
    head_after = _git(repo, "rev-parse", "HEAD").stdout.strip()
    assert head_before == head_after
