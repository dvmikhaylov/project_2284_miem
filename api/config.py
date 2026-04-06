import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"sqlite:///{DATA_DIR / 'documents.sqlite3'}",
)

# Период полураспада веса документа (дней): чем старше загрузка, тем меньше вклад в агрегаты
DECAY_HALF_LIFE_DAYS = float(os.environ.get("DECAY_HALF_LIFE_DAYS", "90"))

CORS_ORIGINS = [
    x.strip()
    for x in os.environ.get(
        "CORS_ORIGINS", "http://localhost:8501,http://127.0.0.1:8501"
    ).split(",")
    if x.strip()
]
