#!/usr/bin/env bash
set -euo pipefail

DB_PATH="${HERMES_ADMIN_DB_PATH:-/opt/hermes-admin/data/hermes_admin.db}"
BACKUP_DIR="${HERMES_ADMIN_BACKUP_DIR:-/opt/hermes-admin/backups}"
KEEP_DAYS="${HERMES_ADMIN_BACKUP_KEEP_DAYS:-14}"

mkdir -p "$BACKUP_DIR"

timestamp="$(date +%Y%m%d-%H%M%S)"
backup_path="$BACKUP_DIR/hermes_admin-$timestamp.db"

sqlite3 "$DB_PATH" ".backup '$backup_path'"
gzip "$backup_path"

find "$BACKUP_DIR" -name "hermes_admin-*.db.gz" -mtime "+$KEEP_DAYS" -delete

echo "Created backup: $backup_path.gz"
