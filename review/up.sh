#!/usr/bin/env bash
set -euo pipefail

review_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

if [[ $# -ne 1 ]]; then
  printf 'Usage: %s ENV_FILE\n' "$0" >&2
  exit 2
fi

set -a
source "$1"
set +a

: "${DSW_VERSION:?Set DSW_VERSION}"
: "${DSW_CLIENT_IMAGE:?Set DSW_CLIENT_IMAGE}"
: "${DSW_REVIEW_TOOL_IMAGE:?Set DSW_REVIEW_TOOL_IMAGE}"
: "${DSW_REVIEW_ORIGIN:?Set DSW_REVIEW_ORIGIN}"
: "${DSW_REVIEW_PORT:?Set DSW_REVIEW_PORT}"
: "${DSW_REVIEW_LOCALE_BUNDLE:?Set DSW_REVIEW_LOCALE_BUNDLE}"
: "${DSW_REVIEW_KNOWLEDGE_MODEL:?Set DSW_REVIEW_KNOWLEDGE_MODEL}"
: "${DSW_ADMIN_PASSWORD:?Set DSW_ADMIN_PASSWORD}"

if [[ "$DSW_REVIEW_ORIGIN" == */ ]]; then
  printf 'DSW_REVIEW_ORIGIN must not end with a slash\n' >&2
  exit 2
fi
if [[ ! "$DSW_REVIEW_PORT" =~ ^[0-9]+$ ]] \
  || ((DSW_REVIEW_PORT < 1 || DSW_REVIEW_PORT > 65535)); then
  printf 'DSW_REVIEW_PORT must be an integer between 1 and 65535\n' >&2
  exit 2
fi
for input in "$DSW_REVIEW_LOCALE_BUNDLE" "$DSW_REVIEW_KNOWLEDGE_MODEL"; do
  if [[ "$input" != /* || ! -f "$input" ]]; then
    printf 'Review input must be an existing absolute file: %s\n' "$input" >&2
    exit 2
  fi
done

project_name=${DSW_REVIEW_PROJECT_NAME:-dsw-translation-review}
export DSW_REVIEW_UID=${DSW_REVIEW_UID:-$(id -u)}
export DSW_REVIEW_GID=${DSW_REVIEW_GID:-$(id -g)}
runtime_dir=${DSW_REVIEW_RUNTIME_DIR:-$review_dir/runtime/default}
mkdir -p -- "$runtime_dir"
runtime_dir=$(cd -- "$runtime_dir" && pwd)
if [[ "$runtime_dir" != "$review_dir/runtime"/* ]]; then
  printf 'DSW_REVIEW_RUNTIME_DIR must be inside %s/runtime\n' "$review_dir" >&2
  exit 2
fi
export DSW_REVIEW_RUNTIME_DIR=$runtime_dir

compose=(
  docker compose
  --project-name "$project_name"
  --file "$review_dir/docker-compose.yml"
)

"${compose[@]}" config --quiet
"${compose[@]}" down --volumes --remove-orphans
rm -rf -- "$runtime_dir"
mkdir -p -- "$runtime_dir"

"${compose[@]}" run --rm review-tool \
  preview-config \
  --output /output/application.yml \
  --client-url "${DSW_REVIEW_ORIGIN}/wizard"
chmod 600 -- "$runtime_dir/application.yml"

"${compose[@]}" up --detach bucket-init minio postgres server client

"${compose[@]}" run --rm review-tool \
  prepare-review \
  --locale-bundle /inputs/locale.zip \
  --knowledge-model /inputs/knowledge-model.json \
  --review-manifest /inputs/pages.yml \
  --output /output/site

"${compose[@]}" up --detach gateway

verify_origin=${DSW_REVIEW_VERIFY_ORIGIN:-http://gateway:8080}
"${compose[@]}" run --rm review-tool \
  verify-review \
  --origin "$verify_origin"

printf 'Review sandbox is ready at %s\n' "$DSW_REVIEW_ORIGIN"
