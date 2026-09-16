#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
backup_root="${project_root}/backups"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="${backup_root}/${timestamp}-$$"
mkdir -p "${backup_dir}"

compose=(
  docker compose
  --file "${project_root}/infra/compose.yaml"
  --env-file "${project_root}/.env"
)

cleanup_failed_backup() {
  if [ ! -f "${backup_dir}/manifest.json" ]; then
    rm -f "${backup_dir}/database.dump" \
      "${backup_dir}/database-counts.json" \
      "${backup_dir}/documents.tar.gz" \
      "${backup_dir}/documents.json"
    rmdir "${backup_dir}" 2>/dev/null || true
  fi
}
trap cleanup_failed_backup EXIT INT TERM

"${compose[@]}" up --detach --wait postgres redis api
source_database="$("${compose[@]}" exec -T postgres sh -eu -c 'printf %s "$POSTGRES_DB"')"

"${compose[@]}" exec -T postgres sh -eu -c \
  'pg_dump --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --format=custom --compress=9' \
  >"${backup_dir}/database.dump"
"${compose[@]}" exec -T postgres sh -eu -c \
  'psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --no-psqlrc --tuples-only --no-align --set ON_ERROR_STOP=1' \
  <"${project_root}/infra/backup-counts.sql" \
  >"${backup_dir}/database-counts.json"

"${compose[@]}" exec -T api \
  python - /app/.storage/documents \
  <"${project_root}/infra/scripts/document_inventory.py" \
  >"${backup_dir}/documents.json"
"${compose[@]}" exec -T api tar -C /app/.storage -czf - documents \
  >"${backup_dir}/documents.tar.gz"

git_revision="$(git -C "${project_root}" rev-parse --verify HEAD 2>/dev/null || printf unknown)"
docker run --rm --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=${backup_dir},dst=/backup" \
  --mount "type=bind,src=${project_root}/infra/scripts/backup_manifest.py,dst=/tool.py,readonly" \
  it-support-agent-api:local \
  python /tool.py create \
    --directory /backup \
    --output /backup/manifest.json \
    --created-at "${timestamp}" \
    --git-revision "${git_revision}" \
    --source-database "${source_database}"

echo "Backup created: ${backup_dir}"
