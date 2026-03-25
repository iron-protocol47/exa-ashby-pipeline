#!/usr/bin/env bash
# GET /catch-up with X-Cron-Secret. Set BASE_URL and CATCH_UP_SECRET.
set -euo pipefail
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
: "${CATCH_UP_SECRET:?}"

curl -fsS -H "X-Cron-Secret: ${CATCH_UP_SECRET}" \
  "${BASE_URL%/}/catch-up"
