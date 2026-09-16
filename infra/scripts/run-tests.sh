#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
compose=(
  docker compose
  --project-name it-support-agent-tests
  --file "${project_root}/infra/compose.yaml"
  --file "${project_root}/infra/compose.test.yaml"
  --env-file "${project_root}/.env"
)

cleanup() {
  "${compose[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

"${compose[@]}" build test-runner
"${compose[@]}" up --detach --wait postgres redis
if [ "$#" -eq 0 ]; then
  set -- /app/tests
fi
"${compose[@]}" run --rm --no-deps test-runner pytest "$@"
if [ "${RUN_FRONTEND:-1}" = "1" ]; then
  make --directory "${project_root}" frontend-check-docker
fi
