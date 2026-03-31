#!/usr/bin/env bash
# Usage: BASE_URL=https://your-app.up.railway.app ./scripts/railway-smoke.sh
# Optional: SMOKE_ADMIN=1 also checks GET /admin (after deploying the admin UI).
set -euo pipefail
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
curl -fsS "${BASE_URL%/}/health"
echo
if [[ "${SMOKE_ADMIN:-}" == "1" ]]; then
  curl -fsS -o /dev/null "${BASE_URL%/}/admin"
  echo "admin page: OK"
fi
