#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  printf 'Usage: %s CLOUDFLARED_IMAGE CONTAINER_NAME LOCAL_PORT\n' "$0" >&2
  exit 2
fi

image=$1
container=$2
port=$3
if [[ ! "$container" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]]; then
  printf 'Tunnel container name contains invalid characters\n' >&2
  exit 2
fi
if [[ ! "$port" =~ ^[0-9]+$ ]] || ((port < 1 || port > 65535)); then
  printf 'Tunnel port must be an integer between 1 and 65535\n' >&2
  exit 2
fi

docker rm --force "$container" >/dev/null 2>&1 || true
docker run \
  --detach \
  --rm \
  --name "$container" \
  --network host \
  "$image" \
  tunnel --no-autoupdate --url "http://127.0.0.1:$port" >/dev/null

for _ in {1..60}; do
  logs=$(docker logs "$container" 2>&1 || true)
  if url=$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' <<< "$logs" | head -n 1) \
    && [[ -n "$url" ]]; then
    printf '%s\n' "$url"
    exit 0
  fi
  if [[ $(docker inspect --format '{{.State.Running}}' "$container" 2>/dev/null || true) != true ]]; then
    printf 'Cloudflare Quick Tunnel stopped before publishing a URL\n%s\n' "$logs" >&2
    exit 1
  fi
  sleep 1
done

printf 'Cloudflare Quick Tunnel did not publish a URL within 60 seconds\n' >&2
docker logs "$container" >&2 || true
exit 1
