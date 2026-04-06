# Если OPENROUTER_API_KEY ещё не в окружении — подхватить key.sh из корня репозитория.
# ROOT задаёт вызывающий скрипт (абсолютный путь к корню проекта).
if [[ -z "${OPENROUTER_API_KEY:-}" && -n "${ROOT:-}" && -f "${ROOT}/key.sh" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT}/key.sh"
  set +a
fi
