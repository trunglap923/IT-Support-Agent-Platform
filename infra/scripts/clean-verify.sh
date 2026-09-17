#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
project_name="it-support-clean-$$"
case "${project_name}" in
  it-support-clean-[0-9]*) ;;
  *) echo "Unsafe clean verification project name" >&2; exit 1 ;;
esac

temporary_dir="$(mktemp -d -t it-support-clean-XXXXXX)"
environment_file="${temporary_dir}/clean.env"
cat >"${environment_file}" <<'EOF'
APP_ENV=development
DEMO_MODE=true
AI_PROVIDER=fake
POSTGRES_DB=it_support_agent
POSTGRES_USER=it_support_agent
POSTGRES_PASSWORD=clean-machine-only-password
DEMO_SEED_PASSWORD=clean-machine-demo-password
FRONTEND_PORT=0
BACKEND_PORT=0
EOF

compose=(
  docker compose
  --project-name "${project_name}"
  --file "${project_root}/infra/compose.yaml"
  --env-file "${environment_file}"
)
ops_compose=(
  docker compose
  --project-name "${project_name}"
  --file "${project_root}/infra/compose.yaml"
  --file "${project_root}/infra/compose.ops.yaml"
  --env-file "${environment_file}"
)

cleanup() {
  "${ops_compose[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
  rm -f "${environment_file}"
  rmdir "${temporary_dir}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

"${compose[@]}" config --quiet
"${compose[@]}" build api frontend
"${compose[@]}" up --detach --wait postgres redis
"${ops_compose[@]}" run --rm migrate
"${compose[@]}" run --rm --no-deps api python -m app.demo_seed_command
"${compose[@]}" up --detach --wait

running_count="$("${compose[@]}" ps --services --filter status=running | wc -l)"
test "${running_count}" -eq 7
"${compose[@]}" exec -T frontend \
  wget --quiet --output-document=- http://127.0.0.1:8080/api/v1/health/ready >/dev/null
echo "Clean verification passed: 7/7 services healthy, migration and seed completed."
