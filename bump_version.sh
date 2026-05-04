#!/usr/bin/env bash
#
# bump_version.sh — single source of truth for version bumps.
#
# Usage:
#   ./bump_version.sh <new_version>
#
# Examples:
#   ./bump_version.sh 0.0.11           # stable release
#   ./bump_version.sh 0.0.11-alpha1    # pre-release
#   ./bump_version.sh 0.0.11-beta2
#   ./bump_version.sh 0.0.11-rc1
#
# What this script does (and the manual edits it replaces):
#   1. Updates the version string in:
#        - custom_components/ctek/manifest.json
#        - custom_components/ctek/const.py
#   2. Date-stamps the "## [x.y.z] - unreleased" CHANGELOG section by
#      renaming it to "## [<new_version>] - YYYY-MM-DD".
#   3. Looks at all `chore(deps): bump <pkg> ...` commits since the last
#      git tag and, if any are present, ensures a single
#        "- Update dependencies (pkg1, pkg2, ...)"
#      line exists under the dated section's `### Changed` block. If a
#      `### Changed` block doesn't exist, one is appended.
#   4. Stages the modified files. Does NOT commit — review first, then
#      commit and tag manually as documented in CLAUDE.md.
#
# Safety: refuses to run with a dirty working tree (other than the files
# this script will touch) so review diffs are clean.

set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <new_version>" >&2
    echo "Examples: 0.0.11 | 0.0.11-alpha1 | 0.0.11-beta2 | 0.0.11-rc1" >&2
    exit 1
fi

NEW_VERSION="$1"

# Allow x.y.z and x.y.z-(alpha|beta|rc)N
if ! [[ $NEW_VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+(-(alpha|beta|rc)[0-9]+)?$ ]]; then
    echo "Error: version must be x.y.z or x.y.z-(alpha|beta|rc)N" >&2
    echo "Got: $NEW_VERSION" >&2
    exit 1
fi

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

MANIFEST="custom_components/ctek/manifest.json"
CONST="custom_components/ctek/const.py"
CHANGELOG="CHANGELOG.md"

for f in "$MANIFEST" "$CONST" "$CHANGELOG"; do
    [[ -f "$f" ]] || { echo "Error: $f not found" >&2; exit 1; }
done

# Refuse to run if anything other than the files we'll touch is dirty.
DIRTY=$(git status --porcelain -- . ":(exclude)$MANIFEST" ":(exclude)$CONST" ":(exclude)$CHANGELOG" || true)
if [[ -n "$DIRTY" ]]; then
    echo "Error: working tree has uncommitted changes outside the files this" >&2
    echo "script will modify. Commit or stash them first:" >&2
    echo "$DIRTY" >&2
    exit 1
fi

# Sync with upstream so the dep-bump scan sees freshly merged PRs. Skip if
# there's no upstream (e.g. detached HEAD or test sandboxes). Set
# BUMP_NO_PULL=1 to opt out (e.g. when intentionally cutting from a stale
# local branch).
if [[ "${BUMP_NO_PULL:-0}" != "1" ]] && git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
    echo "→ git pull --rebase (sync with upstream)"
    git pull --rebase
fi

DATE=$(date +%Y-%m-%d)

echo "→ Updating $MANIFEST"
sed -i "s/\"version\": \".*\"/\"version\": \"$NEW_VERSION\"/" "$MANIFEST"

echo "→ Updating $CONST"
sed -i "s/VERSION = \".*\"/VERSION = \"$NEW_VERSION\"/" "$CONST"

# --- CHANGELOG: date-stamp the unreleased section ----------------------------

# Match either "## [x.y.z] - unreleased" or "## [x.y.z-pre] - unreleased".
UNRELEASED_RE='^## \[[0-9]+\.[0-9]+\.[0-9]+(-(alpha|beta|rc)[0-9]+)?\] - unreleased$'

if ! grep -qE "$UNRELEASED_RE" "$CHANGELOG"; then
    echo "Error: no '## [x.y.z] - unreleased' section found in $CHANGELOG." >&2
    echo "Add one with the entries for this release before running this script." >&2
    exit 1
fi

# Replace the first matching unreleased header with the dated one.
NEW_HEADER="## [$NEW_VERSION] - $DATE"
python3 - "$CHANGELOG" "$NEW_HEADER" <<'PY'
import re, sys
path, new_header = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as f:
    text = f.read()
pattern = re.compile(
    r"^## \[[0-9]+\.[0-9]+\.[0-9]+(-(alpha|beta|rc)[0-9]+)?\] - unreleased$",
    re.MULTILINE,
)
new_text, n = pattern.subn(new_header, text, count=1)
if n != 1:
    sys.exit("failed to rewrite unreleased header")
with open(path, "w", encoding="utf-8") as f:
    f.write(new_text)
PY
echo "→ Renamed unreleased section to: $NEW_HEADER"

# --- Collect dependency bumps since last tag ---------------------------------

LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || true)
if [[ -n "$LAST_TAG" ]]; then
    RANGE="${LAST_TAG}..HEAD"
else
    RANGE="HEAD"
fi

# Extract unique package names from "chore(deps): bump <pkg> from ..." subjects.
# Tolerates "bump <pkg>" and "bump <group>/<pkg>" (GitHub Actions).
# `|| true` so an empty result (grep exit 1 under pipefail) doesn't abort.
DEPS=$(git log --reverse "$RANGE" --pretty=format:'%s' \
    | { grep -E '^chore\(deps[^)]*\): bump ' || true; } \
    | sed -E 's/^chore\(deps[^)]*\): bump ([^[:space:]]+).*/\1/' \
    | awk '!seen[$0]++ {if(out) out=out", "$0; else out=$0} END{print out}')

if [[ -n "$DEPS" ]]; then
    DEPS_LINE="- Update dependencies ($DEPS)"
    echo "→ Detected dependency bumps since ${LAST_TAG:-<root>}: $DEPS"
    python3 - "$CHANGELOG" "$NEW_HEADER" "$DEPS_LINE" <<'PY'
import sys
path, header, deps_line = sys.argv[1], sys.argv[2], sys.argv[3]
with open(path, encoding="utf-8") as f:
    lines = f.read().splitlines()

# Find the section bounds.
try:
    start = next(i for i, l in enumerate(lines) if l == header)
except StopIteration:
    sys.exit("section not found")
end = len(lines)
for i in range(start + 1, len(lines)):
    if lines[i].startswith("## "):
        end = i
        break
section = lines[start:end]

# Skip if a deps line already exists.
if any(l.startswith("- Update dependencies") for l in section):
    print("  (deps line already present, leaving as-is)", file=sys.stderr)
    sys.exit(0)

# Find the "### Changed" subheading or create one.
changed_idx = next(
    (start + i for i, l in enumerate(section) if l.strip() == "### Changed"),
    None,
)
if changed_idx is not None:
    # Insert the line immediately after the heading and any blank line.
    insert_at = changed_idx + 1
    while insert_at < len(lines) and lines[insert_at].strip() == "":
        insert_at += 1
    lines.insert(insert_at, deps_line)
    if insert_at == changed_idx + 1:
        # No blank line between heading and bullet; add one for prettier.
        lines.insert(changed_idx + 1, "")
else:
    # No Changed block; append one before the next ## (or end of section).
    insert_at = end
    while insert_at > start + 1 and lines[insert_at - 1].strip() == "":
        insert_at -= 1
    block = ["", "### Changed", "", deps_line]
    for offset, line in enumerate(block):
        lines.insert(insert_at + offset, line)
with open(path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
PY
else
    echo "→ No dependency bumps since ${LAST_TAG:-<root>}"
fi

# --- Stage and report --------------------------------------------------------

git add "$MANIFEST" "$CONST" "$CHANGELOG"

echo
echo "✓ Bumped to $NEW_VERSION."
echo
echo "Next steps:"
echo "  1. Review the diff:        git diff --staged"
echo "  2. Commit:                 git commit -m \"Bump version to $NEW_VERSION\""
echo "  3. Push:                   git pull --rebase && git push"
echo "  4. Tag + GitHub release    (see CLAUDE.md release flow)"
