#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  printf 'Usage: %s STATE\n' "$0" >&2
  exit 2
fi

state=$1
: "${GH_TOKEN:?Set GH_TOKEN}"
: "${DSW_REVIEW_REPOSITORY:?Set DSW_REVIEW_REPOSITORY}"
: "${DSW_REVIEW_PR_NUMBER:?Set DSW_REVIEW_PR_NUMBER}"
: "${DSW_REVIEW_RUN_ID:?Set DSW_REVIEW_RUN_ID}"
: "${DSW_REVIEW_RUN_URL:?Set DSW_REVIEW_RUN_URL}"
: "${DSW_VERSION:?Set DSW_VERSION}"
: "${DSW_REVIEW_TRANSLATION_REF:?Set DSW_REVIEW_TRANSLATION_REF}"
: "${DSW_REVIEW_REVISION:?Set DSW_REVIEW_REVISION}"
: "${DSW_REVIEW_IDLE_TIMEOUT_MINUTES:?Set DSW_REVIEW_IDLE_TIMEOUT_MINUTES}"
: "${DSW_REVIEW_HARD_TIMEOUT_MINUTES:?Set DSW_REVIEW_HARD_TIMEOUT_MINUTES}"

if [[ ! "$DSW_REVIEW_REPOSITORY" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] \
  || [[ ! "$DSW_REVIEW_PR_NUMBER" =~ ^[0-9]+$ ]] \
  || [[ ! "$DSW_REVIEW_RUN_ID" =~ ^[0-9]+$ ]]; then
  printf 'Invalid pull request coordinates\n' >&2
  exit 2
fi

marker='<!-- dsw-live-preview -->'
run_marker="<!-- dsw-live-preview-run:${DSW_REVIEW_RUN_ID} -->"
comments=$(gh api --paginate \
  "repos/$DSW_REVIEW_REPOSITORY/issues/$DSW_REVIEW_PR_NUMBER/comments")
comment_id=$(jq --raw-output --arg marker "$marker" \
  '.[] | select(.body | contains($marker)) | .id' <<< "$comments" | tail -n 1)

if [[ "$state" != starting ]]; then
  if [[ -z "$comment_id" ]]; then
    exit 0
  fi
  existing=$(gh api "repos/$DSW_REVIEW_REPOSITORY/issues/comments/$comment_id" --jq .body)
  if [[ "$existing" != *"$run_marker"* ]]; then
    exit 0
  fi
fi

case "$state" in
  starting)
    status='⏳ The isolated DSW is starting. This comment will receive the URL when it is ready.'
    ;;
  ready)
    : "${DSW_REVIEW_URL:?Set DSW_REVIEW_URL}"
    status="✅ **[Open the read-only DSW preview]($DSW_REVIEW_URL)**"
    ;;
  ended)
    reason=${DSW_REVIEW_END_REASON:-lifetime limit}
    status="⏹️ The preview ended ($reason). Remove and reapply the \`live-preview\` label to start a new one."
    ;;
  failed)
    status='❌ The preview could not be started. Open the workflow run below for details.'
    ;;
  *)
    printf 'Unknown preview state: %s\n' "$state" >&2
    exit 2
    ;;
esac

safe_dsw_version=$(printf '%s' "$DSW_VERSION" | tr '\r\n`|' '    ')
safe_translation_ref=$(printf '%s' "$DSW_REVIEW_TRANSLATION_REF" | tr '\r\n`|' '    ')
body=$(printf '%s\n%s\n## DSW translation live preview\n\n%s\n\n- DSW: `%s`\n- Translation ref: `%s`\n- Revision: `%s`\n- Lifetime: %s minutes idle, %s minutes maximum\n- [Workflow run](%s)\n\nThe application contains only disposable sample data, and the gateway blocks changes.\n' \
  "$marker" \
  "$run_marker" \
  "$status" \
  "$safe_dsw_version" \
  "$safe_translation_ref" \
  "${DSW_REVIEW_REVISION:0:12}" \
  "$DSW_REVIEW_IDLE_TIMEOUT_MINUTES" \
  "$DSW_REVIEW_HARD_TIMEOUT_MINUTES" \
  "$DSW_REVIEW_RUN_URL")

payload=$(jq --null-input --arg body "$body" '{body: $body}')
if [[ -n "$comment_id" ]]; then
  gh api \
    --method PATCH \
    "repos/$DSW_REVIEW_REPOSITORY/issues/comments/$comment_id" \
    --input - <<< "$payload" >/dev/null
else
  gh api \
    --method POST \
    "repos/$DSW_REVIEW_REPOSITORY/issues/$DSW_REVIEW_PR_NUMBER/comments" \
    --input - <<< "$payload" >/dev/null
fi
