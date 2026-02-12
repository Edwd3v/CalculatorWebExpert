#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "ERROR: No se encontro el entorno virtual en .venv"
  echo "Crea el entorno y dependencias primero:"
  echo "  python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

STRICT_MODE="${HEALTHCHECK_STRICT:-0}"

echo "[healthcheck] Verificando configuracion Django..."
if [[ "$STRICT_MODE" == "1" ]]; then
  .venv/bin/python manage.py check --deploy --fail-level WARNING
else
  .venv/bin/python manage.py check
fi

echo "[healthcheck] Verificando migraciones pendientes..."
if ! .venv/bin/python manage.py migrate --check >/dev/null 2>&1; then
  echo "ERROR: Hay migraciones pendientes."
  echo "Ejecuta: .venv/bin/python manage.py migrate"
  exit 1
fi

echo "[healthcheck] OK: aplicacion lista para ejecutar."
