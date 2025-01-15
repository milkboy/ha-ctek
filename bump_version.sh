#!/bin/bash

# check_version.sh

# Validate input
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <new_version>"
    echo "Example: $0 1.2.3"
    exit 1
fi

NEW_VERSION="$1"

# Validate version format (x.x.x)
if ! [[ $NEW_VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Error: Version must be in format x.x.x (e.g., 1.2.3)"
    exit 1
fi

# Update manifest.json
echo "Updating manifest.json..."
sed -i "s/\"version\": \".*\"/\"version\": \"$NEW_VERSION\"/" custom_components/ctek/manifest.json

# Update const.py
echo "Updating const.py..."
sed -i "s/VERSION = \".*\"/VERSION = \"$NEW_VERSION\"/" custom_components/ctek/const.py

# Update setup.py if it exists
if [ -f "setup.py" ]; then
    echo "Updating setup.py..."
    sed -i "s/version=\".*\"/version=\"$NEW_VERSION\"/" setup.py
fi

# Add entry to CHANGELOG.md
echo "Adding CHANGELOG.md entry..."
DATE=$(date +%Y-%m-%d)
TEMP_FILE=$(mktemp)

# Create new changelog entry
echo "# Changelog

## [$NEW_VERSION] - $DATE
### Added
-

### Fixed
-

### Changed
-

" > "$TEMP_FILE"

# Append existing changelog content
if [ -f CHANGELOG.md ]; then
    tail -n +2 CHANGELOG.md >> "$TEMP_FILE"
fi

mv "$TEMP_FILE" CHANGELOG.md

# Git operations
echo "Creating git commit..."
git add manifest.json custom_components/ctek/const.py CHANGELOG.md
if [ -f "setup.py" ]; then
    git add setup.py
fi

echo "Version bump complete!"
echo "Next steps:"
echo "1. Review the changes (git diff HEAD^) and update CHANGELOG.md"
echo "2. git commit -m \"Bump version to $NEW_VERSION\""
echo "3. Push the changes: git push origin main"
echo "4. Create a GitHub release with the changelog content"
