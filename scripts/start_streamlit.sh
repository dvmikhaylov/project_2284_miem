#!/usr/bin/env bash
# Запуск из корня репозитория (рядом с папкой api/), иначе импорты и пути к pages ломаются.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH=.
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="${PYTHON:-python3}"
fi
exec "$PY" -m streamlit run streamlit_app/Home.py --server.port "${STREAMLIT_PORT:-8501}"
