"""
Конфигурация эксперимента baseline_with_llama_and_rubert
"""
from pathlib import Path

# Корень проекта (родитель этой папки эксперимента)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "validate_data"
OUTPUT_DIR = PROJECT_ROOT / "output"
BUSINESS_PROCESSES_JSON = PROJECT_ROOT / "business_processes" / "business_processes.json"

# Llama.cpp: путь к GGUF-модели (Qwen2.5-0.5B поддерживает русский).
# Скачать: python scripts/download_llama_model.py
# Можно переопределить через env: export LLAMA_MODEL_PATH=/path/to/model.gguf
import os as _os
_models_dir = PROJECT_ROOT / "models"
_env_llama = _os.environ.get("LLAMA_MODEL_PATH")
if _env_llama and Path(_env_llama).exists():
    LLAMA_MODEL_PATH = Path(_env_llama)
else:
    _candidates = [
        _models_dir / "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        _models_dir / "Qwen2.5-0.5B.Q4_K_M.gguf",
    ]
    LLAMA_MODEL_PATH = next((p for p in _candidates if p.exists()), None)
LLAMA_TEMPERATURE = 0.1
LLAMA_MAX_TOKENS = 600

# NER: Qwen 32B (приоритет) или 14B. env: NER_LLAMA_MODEL_PATH=/path/to/model.gguf
_env_ner = _os.environ.get("NER_LLAMA_MODEL_PATH")
if _env_ner and Path(_env_ner).exists():
    NER_LLAMA_MODEL_PATH = Path(_env_ner)
else:
    _ner_candidates = [
        _models_dir / "qwen2.5-32b-instruct-q4_k_m.gguf",
        _models_dir / "Qwen2.5-32B-Instruct-Q4_K_M.gguf",
        _models_dir / "qwen2.5-14b-instruct-q4_k_m.gguf",
        _models_dir / "Qwen2.5-14B-Instruct-Q4_K_M.gguf",
    ]
    NER_LLAMA_MODEL_PATH = next((p for p in _ner_candidates if p.exists()), None)
NER_LLAMA_MAX_TOKENS = 800
NER_LLAMA_TEMPERATURE = 0.0

# OpenRouter: платная модель по умолчанию (стабильнее бесплатной). Ключ: https://openrouter.ai/keys
OPENROUTER_API_KEY = _os.environ.get("OPENROUTER_API_KEY", "").strip() or None
# По умолчанию платная модель (openai/gpt-4o). Можно задать OPENROUTER_MODEL=openai/gpt-oss-120b:free для бесплатной.
OPENROUTER_MODEL = _os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o").strip()
USE_OPENROUTER_FOR_NER = _os.environ.get("USE_OPENROUTER_FOR_NER", "1").strip() in ("1", "true", "yes")
USE_OPENROUTER_FOR_RELATIONS = _os.environ.get("USE_OPENROUTER_FOR_RELATIONS", "1").strip() in ("1", "true", "yes")
# Таймаут (сек), один ретрай при 429/таймауте/пустом ответе, пауза до повтора (сек)
OPENROUTER_TIMEOUT = int(_os.environ.get("OPENROUTER_TIMEOUT", "300"))
OPENROUTER_RETRIES = int(_os.environ.get("OPENROUTER_RETRIES", "1"))
OPENROUTER_RETRY_DELAY = float(_os.environ.get("OPENROUTER_RETRY_DELAY", "10"))

# RuBERT для zero-shot классификации
RUBERT_MODEL = "cointegrated/rubert-tiny2"  # или "DeepPavlov/rubert-base-cased"

MAX_TEXT_LENGTH = 10000
CHUNK_SIZE = 2000

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
