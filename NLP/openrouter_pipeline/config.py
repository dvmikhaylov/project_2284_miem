"""Пути и настройки OpenRouter-пайплайна."""
from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "validate_data"
OUTPUT_DIR = PROJECT_ROOT / "output"
BUSINESS_PROCESSES_JSON = PROJECT_ROOT / "business_processes" / "business_processes.json"

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip() or None
# DeepSeek V3.1 Terminus на OpenRouter; переопределение: OPENROUTER_MODEL=...
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-v3.1-terminus").strip()

OPENROUTER_TIMEOUT = int(os.environ.get("OPENROUTER_TIMEOUT", "600"))
OPENROUTER_RETRIES = int(os.environ.get("OPENROUTER_RETRIES", "1"))
OPENROUTER_RETRY_DELAY = float(os.environ.get("OPENROUTER_RETRY_DELAY", "10"))

# Потолок входного контекста (токены) — как в ошибке OpenRouter для Terminus.
OPENROUTER_MAX_CONTEXT_INPUT_TOKENS = int(os.environ.get("OPENROUTER_MAX_CONTEXT_INPUT_TOKENS", "163840"))
# Оценка символов на токен для длинного русскоязычного текста (запас под токенизатор провайдера).
# Ниже реальной доли «символ/токен» — больше запаса, чтобы не вылезать за потолок провайдера.
OPENROUTER_INPUT_CHARS_PER_TOKEN = float(os.environ.get("OPENROUTER_INPUT_CHARS_PER_TOKEN", "1.06"))
OPENROUTER_CONTEXT_MARGIN_CHARS = int(os.environ.get("OPENROUTER_CONTEXT_MARGIN_CHARS", "8192"))

# Дополнительный потолок длины документа в символах (0 = только лимит контекста выше).
OPENROUTER_MAX_DOC_CHARS = int(os.environ.get("OPENROUTER_MAX_DOC_CHARS", "0"))
OPENROUTER_MAX_ENTITY_TEXT_LEN = int(os.environ.get("OPENROUTER_MAX_ENTITY_TEXT_LEN", "0"))
OPENROUTER_SECOND_PASS_MAX_JSON = int(os.environ.get("OPENROUTER_SECOND_PASS_MAX_JSON", "0"))

# Лимит токенов ответа. DeepSeek V3.1 Terminus — большой контекст; при HTTP 400 у провайдера уменьшите через env.
OPENROUTER_MAX_TOKENS_UNIFIED = int(os.environ.get("OPENROUTER_MAX_TOKENS_UNIFIED", "131072"))
OPENROUTER_MAX_TOKENS_SECOND = int(os.environ.get("OPENROUTER_MAX_TOKENS_SECOND", "131072"))
# Отдельный лимит ответа для 2-го прохода (нормализация графа), чтобы не раздувать запрос к контексту.
OPENROUTER_MAX_TOKENS_SECOND_PASS = int(os.environ.get("OPENROUTER_MAX_TOKENS_SECOND_PASS", "12000"))

# Пустая строка в env не должна отключать проход (get не подставляет default, если ключ есть).
_sp = os.environ.get("OPENROUTER_SECOND_PASS")
if _sp is None or not str(_sp).strip():
    OPENROUTER_SECOND_PASS = True
else:
    OPENROUTER_SECOND_PASS = str(_sp).strip().lower() in ("1", "true", "yes")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
