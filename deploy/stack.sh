#!/usr/bin/env bash
# Start/stop ONE benchmarked stack on the SUT. Runs on DEV_SERVER (needs only Docker).
#
#   stack.sh up <stack>        PostgreSQL + schema/seed, then the stack's API container; waits for :8080
#   stack.sh down [<stack>]    stop the API container (PostgreSQL keeps running)
#   stack.sh restart <stack>   down, restart PostgreSQL (cold shared buffers), up. Used before confirmation runs
#   stack.sh status            what is running
#   stack.sh logs [<stack>]    tail the API container log
#
# Image resolution: deploy/images.lock ("<stack>=<image@sha256:digest>", written by the release
# pipeline) wins; otherwise ghcr.io/<repo>/<stack>:${IMAGE_TAG:-develop} (public, no login needed).
# Only one stack runs at a time (benchmark-rules.md §2).
set -euo pipefail

DEPLOY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACKS=(python-fastapi node-fastify java-springboot csharp-dotnet go-gin rust-axum)
REGISTRY="${REGISTRY:-ghcr.io/jalalazhmatkhan/api-benchmarking}"
COMPOSE=(docker compose -f "${DEPLOY}/compose.yaml")

log() { printf '[stack] %s\n' "$*" >&2; }

check_stack() {
  local s
  for s in "${STACKS[@]}"; do [[ "$s" == "$1" ]] && return 0; done
  echo "unknown stack '$1' (one of: ${STACKS[*]})" >&2; exit 2
}

image_for() {
  local line
  if [[ -f "${DEPLOY}/images.lock" ]] && line="$(grep -E "^$1=" "${DEPLOY}/images.lock")"; then
    echo "${line#*=}"
  else
    echo "${REGISTRY}/$1:${IMAGE_TAG:-develop}"
  fi
}

wait_port() { # host port seconds
  local i
  for ((i = 0; i < $3; i++)); do
    (exec 3<>"/dev/tcp/$1/$2") 2>/dev/null && return 0
    sleep 1
  done
  return 1
}

wait_postgres() {
  local i
  for i in $(seq 1 60); do
    [[ "$(docker inspect -f '{{.State.Health.Status}}' bench-postgres 2>/dev/null)" == "healthy" ]] && return 0
    sleep 1
  done
  echo "PostgreSQL did not become healthy" >&2; docker logs --tail 30 bench-postgres >&2 || true; exit 1
}

stop_api() { "${COMPOSE[@]}" rm -sf api >/dev/null 2>&1 || true; }

up() {
  check_stack "$1"
  local image env_file="${DEPLOY}/stacks/$1.env"
  [[ -f "$env_file" ]] || env_file="${DEPLOY}/stacks/default.env"
  image="$(image_for "$1")"
  log "stack $1: image $image"
  stop_api
  "${COMPOSE[@]}" up -d postgres >/dev/null
  wait_postgres
  "${COMPOSE[@]}" run --rm db-init >/dev/null
  API_IMAGE="$image" API_ENV_FILE="$env_file" "${COMPOSE[@]}" --profile api pull api >/dev/null
  API_IMAGE="$image" API_ENV_FILE="$env_file" "${COMPOSE[@]}" --profile api up -d api >/dev/null
  if ! wait_port 127.0.0.1 8080 90; then
    docker logs --tail 40 bench-api >&2 || true
    echo "$1 did not open :8080 in 90 s" >&2; exit 1
  fi
  log "$1 is up: $(docker inspect -f '{{.Image}}' bench-api | cut -c1-19), pool connections: $(docker exec bench-postgres psql -U monitor -d bench -tAc "SELECT count(*) FROM pg_stat_activity WHERE usename='bench' AND backend_type='client backend'")"
}

case "${1:-}" in
  up)      up "${2:?usage: stack.sh up <stack>}" ;;
  down)    stop_api; log "api stopped" ;;
  restart) check_stack "${2:?usage: stack.sh restart <stack>}"; stop_api
           docker restart bench-postgres >/dev/null 2>&1 || "${COMPOSE[@]}" up -d postgres >/dev/null
           wait_postgres; up "$2" ;;
  status)  docker ps --filter name=bench- --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' ;;
  logs)    docker logs --tail 100 bench-api ;;
  *) echo "usage: stack.sh up|down|restart|status|logs [<stack>]" >&2; exit 2 ;;
esac
