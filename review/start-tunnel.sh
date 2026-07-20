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

attempts=5
polls_per_attempt=60
last_logs=

docker rm --force "$container" >/dev/null 2>&1 || true
for ((attempt = 1; attempt <= attempts; attempt++)); do
  last_logs=
  docker run \
    --detach \
    --name "$container" \
    --network host \
    "$image" \
    tunnel --no-autoupdate --url "http://127.0.0.1:$port" >/dev/null

  for ((poll = 1; poll <= polls_per_attempt; poll++)); do
    logs=$(docker logs "$container" 2>&1 || true)
    if url=$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' <<< "$logs" | head -n 1) \
      && [[ -n "$url" ]]; then
      printf '%s\n' "$url"
      exit 0
    fi
    if [[ $(docker inspect --format '{{.State.Running}}' "$container" 2>/dev/null || true) != true ]]; then
      last_logs=$logs
      break
    fi
    sleep 1
  done

  if [[ -z "$last_logs" ]]; then
    last_logs=$(docker logs "$container" 2>&1 || true)
  fi
  docker rm --force "$container" >/dev/null 2>&1 || true
  if ((attempt < attempts)); then
    retry_delay=$((attempt * 5))
    printf 'Cloudflare Quick Tunnel attempt %d failed; retrying in %d seconds\n' \
      "$attempt" "$retry_delay" >&2
    sleep "$retry_delay"
  fi
done

printf 'Cloudflare Quick Tunnel failed after %d attempts\n%s\n' "$attempts" "$last_logs" >&2
exit 1
