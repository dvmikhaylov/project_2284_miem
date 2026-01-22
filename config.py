"""
Конфигурация пайплайна извлечения информации из документов
"""
import os
from pathlib import Path

# Пути
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "validate_data"
BUSINESS_PROCESSES_FILE = PROJECT_ROOT / "business_processes.txt"
OUTPUT_DIR = PROJECT_ROOT / "output"

# Создаем директорию для вывода
OUTPUT_DIR.mkdir(exist_ok=True)

# Настройки моделей
USE_GPU = True  # Использовать MPS (Metal Performance Shaders) на Mac
NER_MODEL = "natasha"  # "natasha" или "spacy"
RELATION_MODEL = "llm"  # "llm" или "pattern"

# Настройки LLM (если используется)
LLM_MODEL_PATH = None  # Путь к локальной модели, если используется
LLM_TEMPERATURE = 0.1
LLM_MAX_TOKENS = 2000

# Настройки обработки
MAX_TEXT_LENGTH = 10000  # Максимальная длина текста для обработки
CHUNK_SIZE = 2000  # Размер чанков для обработки длинных документов
