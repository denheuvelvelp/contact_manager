#!/bin/bash
# Start script voor de Coöperatieve Vereniging app
# Luistert op 0.0.0.0 zodat deze bereikbaar is via het netwerk

cd "$(dirname "$0")"

PORT="${PORT:-8080}"
HOST="${HOST:-0.0.0.0}"

echo "=========================================================="
echo " Huismeester Contactmanager - Coöperatieve Vereniging"
echo " Luistert op: http://${HOST}:${PORT}"
echo " Netwerk URL: http://10.13.20.161:${PORT}"
echo "=========================================================="

exec python3 -m uvicorn apps.cooperatie.main:app --host "$HOST" --port "$PORT" --reload

