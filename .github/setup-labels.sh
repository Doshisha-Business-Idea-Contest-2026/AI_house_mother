#!/usr/bin/env bash
# Create the standard issue labels for this repository.
#
# Usage:
#   gh auth login        # authenticate first
#   ./.github/setup-labels.sh
#
# Re-running is safe: `--force` updates existing labels instead of failing.

set -euo pipefail

REPO="Doshisha-Business-Idea-Contest-2026/AI_house_mother"

create() {
    local name="$1" color="$2" desc="$3"
    gh label create "$name" --color "$color" --description "$desc" --repo "$REPO" --force
}

# Type labels (aligned with branch naming and issue title prefixes)
create "type: feat"     "0e8a16" "New feature"
create "type: bug"      "d73a4a" "Bug fix"
create "type: refactor" "1d76db" "Refactoring"
create "type: docs"     "0075ca" "Documentation"
create "type: chore"    "cfd3d7" "Chores / maintenance"

# Priority labels
create "priority: high"   "b60205" "Blocks demo / MVP. Top priority."
create "priority: medium" "fbca04" "Normal priority."
create "priority: low"    "c2e0c6" "Nice to have."

echo "Done. Verify with: gh label list --repo ${REPO}"
