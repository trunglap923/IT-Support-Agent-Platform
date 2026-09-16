#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
compose=(
  docker compose
  --project-name it-support-agent-eval
  --file "${project_root}/infra/compose.yaml"
  --file "${project_root}/infra/compose.test.yaml"
  --env-file "${project_root}/.env"
)

cleanup() {
  "${compose[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

"${compose[@]}" build test-runner
"${compose[@]}" run --rm --no-deps test-runner \
  python -m evals.runner.validate_cases
"${compose[@]}" run --rm --no-deps test-runner \
  python -m evals.runner.cli \
  --mode fake \
  --split development \
  --output /tmp/agent-evaluation-fake.json
