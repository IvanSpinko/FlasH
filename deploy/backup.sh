#!/usr/bin/env bash
# Save all decks and progress (the flash-data volume) to a .tar.gz file.
# Run it on the server:   ~/FlasH/deploy/backup.sh [folder]     (default: ~/flash-backups)
# Restore one:            ~/FlasH/deploy/backup.sh --restore ~/flash-backups/flash-data-....tar.gz
# Keep copies somewhere else too (your computer, S3): a backup on the same disk dies with it.
set -euo pipefail

cd "$(dirname "$0")/.."
project="$(basename "$PWD" | tr '[:upper:]' '[:lower:]')"
volume="${COMPOSE_PROJECT_NAME:-$project}_flash-data"
compose=(docker compose -f compose.yaml -f compose.prod.yaml)

if [[ "${1:-}" == "--restore" ]]; then
    file="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"
    echo "==> Restoring $file into $volume (the API is stopped meanwhile)"
    "${compose[@]}" stop api
    docker run --rm -v "$volume":/data -v "$(dirname "$file")":/backup:ro alpine \
        sh -c "rm -rf /data/* && tar xzf '/backup/$(basename "$file")' -C /data"
    "${compose[@]}" start api
    echo "==> Restored"
    exit 0
fi

folder="${1:-$HOME/flash-backups}"
mkdir -p "$folder"
name="flash-data-$(date +%Y%m%d-%H%M%S).tar.gz"
docker run --rm -v "$volume":/data:ro -v "$folder":/backup alpine tar czf "/backup/$name" -C /data .
echo "==> Saved $folder/$name"

# Keep the 14 newest backups (the names have no spaces, so ls is safe here).
# shellcheck disable=SC2012
ls -1t "$folder"/flash-data-*.tar.gz | tail -n +15 | xargs -r rm --
