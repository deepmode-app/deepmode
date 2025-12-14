#!/usr/bin/env bash
set -euo pipefail

# Resolve base URL: prefer BASE_URL, fallback to APP_BASE_URL
if [ -n "${BASE_URL:-}" ]; then
  API_BASE_URL="${BASE_URL}"
elif [ -n "${APP_BASE_URL:-}" ]; then
  API_BASE_URL="${APP_BASE_URL}"
else
  echo "Error: Either BASE_URL or APP_BASE_URL environment variable must be set" >&2
  exit 1
fi

# Validate required environment variable
if [ -z "${JOBS_SECRET:-}" ]; then
  echo "Error: JOBS_SECRET environment variable is not set" >&2
  exit 1
fi

# Call the endpoint (curl -f fails on HTTP error codes)
curl -sS -f -X POST "${API_BASE_URL}/jobs/daily-streak-digest" \
  -H "X-JOBS-SECRET: ${JOBS_SECRET}" \
  -H "Content-Type: application/json"

echo "OK: daily digest triggered"
