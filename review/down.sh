#!/usr/bin/env bash
set -euo pipefail

review_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

if [[ $# -gt 1 ]]; then
  printf 'Usage: %s [ENV_FILE]\n' "$0" >&2
  exit 2
fi

if [[ $# -eq 1 ]]; then
  set -a
  source "$1"
  set +a
fi

project_name=${DSW_REVIEW_PROJECT_NAME:-dsw-translation-review}
runtime_dir=${DSW_REVIEW_RUNTIME_DIR:-$review_dir/runtime/default}
mkdir -p -- "$runtime_dir"
runtime_dir=$(cd -- "$runtime_dir" && pwd)
if [[ "$runtime_dir" != "$review_dir/runtime"/* ]]; then
  printf 'DSW_REVIEW_RUNTIME_DIR must be inside %s/runtime\n' "$review_dir" >&2
  exit 2
fi
export DSW_REVIEW_RUNTIME_DIR=$runtime_dir

docker compose \
  --project-name "$project_name" \
  --file "$review_dir/docker-compose.yml" \
  down --volumes --remove-orphans

rm -rf -- "$runtime_dir"
