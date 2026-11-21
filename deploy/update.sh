#!/usr/bin/env bash
# Update a running FlasH server to the newest code and restart what changed.
# Run it on the server, from anywhere:   ~/FlasH/deploy/update.sh [branch]
# The deploy workflow (.github/workflows/deploy.yml) runs the same script over SSH.
set -euo pipefail

cd "$(dirname "$0")/.."
branch="${1:-main}"

echo "==> Getting the newest code ($branch)"
git fetch --prune origin
git checkout "$branch"
git merge --ff-only "origin/$branch"

echo "==> Building and starting the containers"
compose=(docker compose -f compose.yaml -f compose.prod.yaml)
"${compose[@]}" up -d --build --wait --remove-orphans

echo "==> Removing old images"
docker image prune -f >/dev/null

"${compose[@]}" ps
echo "==> Done: $(git log -1 --format='%h %s')"
