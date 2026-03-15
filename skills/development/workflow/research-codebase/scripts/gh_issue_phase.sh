#!/usr/bin/env bash
set -euo pipefail

# GitHub Issue phase tracking for the development workflow.
# Each workflow phase posts a structured comment with an HTML marker
# so re-running a phase updates the existing comment instead of duplicating.

usage() {
  cat >&2 <<'EOF'
Usage: gh_issue_phase.sh <action> [args...]

Actions:
  create-issue "Title"       Create issue (body from stdin), prints issue number
  post-phase <issue> <phase> Post/update phase comment (content from stdin)
  set-label <issue> <label>  Set phase label (removes old phase:* labels)
  get-issue <issue>          Print issue body + all comments
  close-issue <issue>        Close the issue

<issue> accepts a number (42) or URL (https://github.com/owner/repo/issues/42).
EOF
  exit 1
}

# Resolve an issue reference to a number.
# Accepts: 42, https://github.com/owner/repo/issues/42
resolve_issue() {
  local ref="$1"
  if [[ "$ref" =~ ^[0-9]+$ ]]; then
    echo "$ref"
  elif [[ "$ref" =~ ^https://github\.com/[^/]+/[^/]+/issues/([0-9]+) ]]; then
    echo "${BASH_REMATCH[1]}"
  else
    echo "Invalid issue reference: $ref (expected number or GitHub URL)" >&2
    exit 1
  fi
}

# Get label color by phase name.
label_color() {
  local label="$1"
  case "$label" in
    phase:research)   echo "1d76db" ;;
    phase:brainstorm) echo "5319e7" ;;
    phase:design)     echo "d93f0b" ;;
    phase:planning)   echo "fbca04" ;;
    phase:review)     echo "bfdadc" ;;
    phase:done)       echo "0e8a16" ;;
    *)                echo "ededed" ;;
  esac
}

# Ensure a label exists on the repo, creating it if needed.
ensure_label() {
  local label="$1"
  local color
  color=$(label_color "$label")

  if ! gh label list --search "$label" --json name -q '.[].name' | grep -qx "$label" 2>/dev/null; then
    gh label create "$label" --color "$color" --description "Workflow phase" 2>/dev/null || true
  fi
}

# --- Actions ---

action_create_issue() {
  if [[ $# -lt 1 ]]; then
    echo "Usage: gh_issue_phase.sh create-issue \"Title\"" >&2
    exit 1
  fi
  local title="$1"
  local body
  body=$(cat)

  local number
  number=$(gh issue create --title "$title" --body "$body" | grep -oE '[0-9]+$')
  echo "$number"
}

action_post_phase() {
  if [[ $# -lt 2 ]]; then
    echo "Usage: gh_issue_phase.sh post-phase <issue> <phase>" >&2
    exit 1
  fi
  local issue_number
  issue_number=$(resolve_issue "$1")
  local phase="$2"
  local marker="<!-- agr-phase:${phase} -->"
  local content
  content=$(cat)
  local phase_title
  phase_title="$(printf '%s' "${phase:0:1}" | tr '[:lower:]' '[:upper:]')${phase:1}"
  local body="${marker}
## ${phase_title} Phase

${content}"

  # Look for existing comment with this marker
  local comment_id
  comment_id=$(gh api "repos/{owner}/{repo}/issues/${issue_number}/comments" \
    --paginate --jq ".[] | select(.body | contains(\"${marker}\")) | .id" 2>/dev/null | head -1)

  if [[ -n "$comment_id" ]]; then
    # Update existing comment
    gh api "repos/{owner}/{repo}/issues/comments/${comment_id}" \
      --method PATCH --field body="$body" --silent
  else
    # Create new comment
    gh api "repos/{owner}/{repo}/issues/${issue_number}/comments" \
      --method POST --field body="$body" --silent
  fi
}

action_set_label() {
  if [[ $# -lt 2 ]]; then
    echo "Usage: gh_issue_phase.sh set-label <issue> <label>" >&2
    exit 1
  fi
  local issue_number
  issue_number=$(resolve_issue "$1")
  local new_label="$2"

  ensure_label "$new_label"

  # Remove existing phase:* labels
  local existing_labels
  existing_labels=$(gh api "repos/{owner}/{repo}/issues/${issue_number}/labels" \
    --jq '.[].name' 2>/dev/null || true)

  while IFS= read -r label; do
    if [[ "$label" == phase:* && "$label" != "$new_label" ]]; then
      gh api "repos/{owner}/{repo}/issues/${issue_number}/labels/${label}" \
        --method DELETE --silent 2>/dev/null || true
    fi
  done <<< "$existing_labels"

  # Add new label
  gh api "repos/{owner}/{repo}/issues/${issue_number}/labels" \
    --method POST --field "labels[]=$new_label" --silent
}

action_get_issue() {
  if [[ $# -lt 1 ]]; then
    echo "Usage: gh_issue_phase.sh get-issue <issue>" >&2
    exit 1
  fi
  local issue_number
  issue_number=$(resolve_issue "$1")

  gh issue view "$issue_number" --comments
}

action_close_issue() {
  if [[ $# -lt 1 ]]; then
    echo "Usage: gh_issue_phase.sh close-issue <issue>" >&2
    exit 1
  fi
  local issue_number
  issue_number=$(resolve_issue "$1")

  gh issue close "$issue_number"
}

# --- Main ---

if [[ $# -lt 1 ]]; then
  usage
fi

action="$1"
shift

case "$action" in
  create-issue) action_create_issue "$@" ;;
  post-phase)   action_post_phase "$@" ;;
  set-label)    action_set_label "$@" ;;
  get-issue)    action_get_issue "$@" ;;
  close-issue)  action_close_issue "$@" ;;
  *)
    echo "Unknown action: $action" >&2
    usage
    ;;
esac
