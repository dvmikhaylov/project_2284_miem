"""
Конфигурация пайплайна извлечения информации из документов (baseline)
"""
import os
from pathlib import Path

# Корень проекта (родитель папки baseline)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "validate_data"
BUSINESS_PROCESSES_FILE = PROJECT_ROOT / "business_processes" / "business_processes.txt"
OUTPUT_DIR = PROJECT_ROOT / "output"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Настройки моделей
USE_GPU = True
NER_MODEL = "natasha"
RELATION_MODEL = "pattern"

# Настройки обработки
MAX_TEXT_LENGTH = 10000
CHUNK_SIZE = 2000
