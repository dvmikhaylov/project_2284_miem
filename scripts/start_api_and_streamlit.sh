#!/usr/bin/env bash
# API + Streamlit в одном терминале. Ctrl+C корректно завершает оба процесса.
# Не используйте Ctrl+Z — процессы останутся в фоне и займут порты.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH=.
# shellcheck disable=SC1091
source "$(cd "$(dirname "$0")" && pwd)/_openrouter_env.sh"

API_PORT="${API_PORT:-8000}"
API_HOST="${API_HOST:-127.0.0.1}"
STREAMLIT_PORT="${STREAMLIT_PORT:-8501}"
# Streamlit ходит на API по loopback, даже если API слушает 0.0.0.0
export API_URL="${API_URL:-http://127.0.0.1:${API_PORT}}"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="${PYTHON:-python3}"
fi

if ! "$PY" -c "import uvicorn, streamlit" 2>/dev/null; then
  echo "Нужны пакеты в .venv: pip install -r requirements.txt" >&2
  exit 1
fi
if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
  echo "Предупреждение: OPENROUTER_API_KEY не задан — key.sh в корне или export перед запуском." >&2
fi

cleanup() {
  if [[ -n "${API_PID:-}" ]] && kill -0 "$API_PID" 2>/dev/null; then
    echo "" >&2
    echo "Останавливаю API (pid $API_PID)..." >&2
    kill "$API_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "API:  http://${API_HOST}:${API_PORT}  (health: ${API_URL}/health)"
echo "UI:   http://127.0.0.1:${STREAMLIT_PORT}"
echo "API_URL для Streamlit: $API_URL"
echo ""

UVICORN_ARGS=()
if [[ "${API_RELOAD:-}" == 1 ]]; then
  UVICORN_ARGS+=(--reload)
fi
"$PY" -m uvicorn api.main:app --host "$API_HOST" --port "$API_PORT" "${UVICORN_ARGS[@]}" &
API_PID=$!

ok=0
for _ in $(seq 1 60); do
  if "$PY" -c "import urllib.request; urllib.request.urlopen('${API_URL}/health', timeout=2).read()" 2>/dev/null; then
    ok=1
    break
  fi
  if ! kill -0 "$API_PID" 2>/dev/null; then
    echo "Процесс API завершился до готовности. Смотрите ошибки выше." >&2
    exit 1
  fi
  sleep 0.5
done

if [[ "$ok" != 1 ]]; then
  echo "API не ответил на ${API_URL}/health за 30 с." >&2
  exit 1
fi

echo "API отвечает. Запускаю Streamlit (Ctrl+C — выход и остановка API)..."
"$PY" -m streamlit run streamlit_app/Home.py --server.port "$STREAMLIT_PORT"
