#!/usr/bin/env bash
# Используем Python из .venv, если он есть — иначе команда `uvicorn` из pipx
# поднимает приложение без fastapi из проекта → ModuleNotFoundError.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH=.
# shellcheck disable=SC1091
source "$(cd "$(dirname "$0")" && pwd)/_openrouter_env.sh"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="${PYTHON:-python3}"
fi
if ! "$PY" -c "import uvicorn" 2>/dev/null; then
  echo "В этом Python нет пакета uvicorn." >&2
  echo "Установите зависимости проекта, например:" >&2
  echo "  cd \"$ROOT\" && .venv/bin/pip install -r requirements.txt" >&2
  echo "или: source .venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi
if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
  echo "Предупреждение: OPENROUTER_API_KEY не задан — положите key.sh в корень репозитория или export OPENROUTER_API_KEY=..." >&2
fi
# По умолчанию 127.0.0.1 — в браузере открывайте http://127.0.0.1:PORT (не 0.0.0.0).
# Доступ с других машин в сети: API_HOST=0.0.0.0 ./scripts/start_api.sh
exec "$PY" -m uvicorn api.main:app --host "${API_HOST:-127.0.0.1}" --port "${API_PORT:-8000}"
