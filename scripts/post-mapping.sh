#!/usr/bin/env bash
# POST /api/mappings (HTTP Basic). Set BASE_URL, ADMIN_BASIC_USER, ADMIN_BASIC_PASSWORD, and body vars.
set -euo pipefail
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
: "${ADMIN_BASIC_USER:?}"
: "${ADMIN_BASIC_PASSWORD:?}"
: "${WEBSET_ID:?}"
: "${ASHBY_JOB_ID:?}"
: "${SOURCE_TAG:?}"

curl -fsS -u "${ADMIN_BASIC_USER}:${ADMIN_BASIC_PASSWORD}" \
  -H "Content-Type: application/json" \
  -d "{\"webset_id\":\"${WEBSET_ID}\",\"ashby_job_id\":\"${ASHBY_JOB_ID}\",\"source_tag\":\"${SOURCE_TAG}\",\"active\":true}" \
  "${BASE_URL%/}/api/mappings"
