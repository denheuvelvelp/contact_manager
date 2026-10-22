#!/bin/bash
# Start script voor de Vereniging van Eigenaren (VvE) app
# Luistert op poort 8081 (Coöperatie luistert op 8080)

cd "$(dirname "$0")"

PORT="${PORT:-8081}"
HOST="${HOST:-0.0.0.0}"

if [ -f "config/workspace-sync-key.json" ]; then
    export GOOGLE_WORKSPACE_CREDENTIALS_PATH="$(pwd)/config/workspace-sync-key.json"
    export GOOGLE_WORKSPACE_ADMIN_EMAIL="${GOOGLE_WORKSPACE_ADMIN_EMAIL:-alberdao@denheuvelvelp.nl}"
    export GOOGLE_WORKSPACE_DOMAIN="denheuvelvelp.nl"
fi

echo "=========================================================="
echo " Huismeester Contactmanager - Vereniging van Eigenaren (VvE)"
echo " Luistert op: http://${HOST}:${PORT}"
echo " Netwerk URL: http://10.13.20.161:${PORT}"
echo "=========================================================="

exec python3 -m uvicorn apps.vve.main:app --host "$HOST" --port "$PORT" --reload

