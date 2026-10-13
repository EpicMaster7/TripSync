#!/usr/bin/env sh
set -eu
: "${DEMO_PASSWORD:?Set DEMO_PASSWORD with a fresh 10+ character local demo password}"
docker compose up --build -d --wait
docker compose exec -T -e DEMO_PASSWORD="$DEMO_PASSWORD" backend python -m app.demo_seed
printf '\nTripSync: http://localhost:5173\nExample login: alex@tripsync.example.test (DEMO_PASSWORD)\nAPI reference: http://localhost:8000/docs\n'
