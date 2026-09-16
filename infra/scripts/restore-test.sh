#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
backup_root="${project_root}/backups"
requested_backup="${BACKUP_DIR:-${1:-}}"
if [ -z "${requested_backup}" ]; then
  if [ ! -d "${backup_root}" ]; then
    echo "No backup found. Run 'make backup' first." >&2
    exit 1
  fi
  requested_backup="$(find "${backup_root}" -mindepth 1 -maxdepth 1 -type d -printf '%p\n' 2>/dev/null | sort | tail -n 1)"
fi
if [ -z "${requested_backup}" ]; then
  echo "No backup found. Run 'make backup' first." >&2
  exit 1
fi
backup_dir="$(realpath "${requested_backup}")"
case "${backup_dir}" in
  "${backup_root}"/*) ;;
  *) echo "Backup must be a directory below ${backup_root}" >&2; exit 1 ;;
esac
test -d "${backup_dir}"

compose=(
  docker compose
  --file "${project_root}/infra/compose.yaml"
  --env-file "${project_root}/.env"
)
restore_database="restore_test_$(date -u +%Y%m%d%H%M%S)_$$"
document_volume="it-support-restore-$$-documents"
case "${restore_database}" in restore_test_[0-9]*) ;; *) exit 1 ;; esac
case "${document_volume}" in it-support-restore-[0-9]*-documents) ;; *) exit 1 ;; esac
temporary_dir="$(mktemp -d -t it-support-restore-XXXXXX)"

cleanup() {
  "${compose[@]}" exec -T --env "TARGET_DATABASE=${restore_database}" postgres sh -eu -c \
    'dropdb --if-exists --force --username "$POSTGRES_USER" "$TARGET_DATABASE"' \
    >/dev/null 2>&1 || true
  docker volume rm --force "${document_volume}" >/dev/null 2>&1 || true
  rm -f "${temporary_dir}/database-counts.json" "${temporary_dir}/documents.json"
  rmdir "${temporary_dir}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

docker run --rm --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=${backup_dir},dst=/backup,readonly" \
  --mount "type=bind,src=${project_root}/infra/scripts/backup_manifest.py,dst=/tool.py,readonly" \
  it-support-agent-api:local \
  python /tool.py verify --directory /backup

"${compose[@]}" up --detach --wait postgres
"${compose[@]}" exec -T --env "TARGET_DATABASE=${restore_database}" postgres sh -eu -c \
  'createdb --template=template0 --username "$POSTGRES_USER" "$TARGET_DATABASE"'
"${compose[@]}" exec -T --env "TARGET_DATABASE=${restore_database}" postgres sh -eu -c \
  'pg_restore --exit-on-error --no-owner --no-privileges --username "$POSTGRES_USER" --dbname "$TARGET_DATABASE"' \
  <"${backup_dir}/database.dump"
"${compose[@]}" exec -T --env "TARGET_DATABASE=${restore_database}" postgres sh -eu -c \
  'psql --username "$POSTGRES_USER" --dbname "$TARGET_DATABASE" --no-psqlrc --tuples-only --no-align --set ON_ERROR_STOP=1' \
  <"${project_root}/infra/backup-counts.sql" \
  >"${temporary_dir}/database-counts.json"
cmp --silent "${backup_dir}/database-counts.json" "${temporary_dir}/database-counts.json"

docker volume create "${document_volume}" >/dev/null
docker run --rm --user 0:0 --interactive \
  --mount "type=volume,src=${document_volume},dst=/restore" \
  it-support-agent-api:local \
  tar -C /restore -xzf - \
  <"${backup_dir}/documents.tar.gz"
docker run --rm --interactive \
  --mount "type=volume,src=${document_volume},dst=/restore,readonly" \
  it-support-agent-api:local \
  python - /restore/documents \
  <"${project_root}/infra/scripts/document_inventory.py" \
  >"${temporary_dir}/documents.json"
cmp --silent "${backup_dir}/documents.json" "${temporary_dir}/documents.json"

echo "Restore drill passed in isolated database ${restore_database} and volume ${document_volume}."
