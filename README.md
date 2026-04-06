# Анализ документов и бизнес-процессов

Сервис извлекает из договоров и смежных документов сущности, связи, цепочки действий и привязки к справочнику процессов (LLM), сохраняет результат в SQLite и отдаёт агрегаты в REST API и в веб-интерфейсе (Streamlit).

## Требования

- Python 3.11+ (рекомендуется)
- Зависимости: `pip install -r requirements.txt`

## Установка

```bash
cd /path/to/repo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Для обработки документов задайте ключ API модели (см. таблицу ниже). Файл `key.sh` в корне подхватывают `scripts/start_api.sh` и `scripts/start_api_and_streamlit.sh`, если переменная ещё не экспортирована в окружении.

## Запуск (корень репозитория)

Все команды ниже выполняйте из каталога, где лежат `api/` и `NLP/`, с `PYTHONPATH=.` или активированным venv из корня.

**API и UI одной командой (рекомендуется):**

```bash
chmod +x scripts/start_api_and_streamlit.sh   # один раз
./scripts/start_api_and_streamlit.sh
```

**Только API:**

```bash
export PYTHONPATH=.
./scripts/start_api.sh
# или: python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

- Документация API: `http://127.0.0.1:8000/docs`
- Health: `GET /health`

**Только Streamlit** (API должен быть доступен по `API_URL`):

```bash
export API_URL=http://127.0.0.1:8000
./scripts/start_streamlit.sh
```

Порты: `API_PORT`, `STREAMLIT_PORT`, хост API: `API_HOST`. Остановка процессов — **Ctrl+C** (не Ctrl+Z).

**CLI извлечения без записи в БД:**

```bash
python run.py --file path/to/document.docx
```

## Структура репозитория

| Каталог / файл | Назначение |
|----------------|------------|
| `api/` | FastAPI, SQLAlchemy, миграции SQLite, агрегаты дашборда |
| `NLP/` | Чтение docx/pdf/txt, промпты, вызов LLM, постобработка JSON |
| `streamlit_app/` | UI: дашборд, загрузка, просмотр документов |
| `business_processes/business_processes.json` | Справочник процессов и приоритеты |
| `data/` | БД SQLite (в `.gitignore`) |
| `tests/` | Смоук-тесты API |

## Переменные окружения

Полный список и значения по умолчанию для пайплайна извлечения — в `NLP/.../config.py` (подпакет пайплайна в каталоге `NLP/`).

**Минимально для работы ingest / CLI:**

| Переменная | Описание |
|------------|----------|
| `OPENROUTER_API_KEY` | Секрет HTTP API модели (обязателен для обработки документов) |
| `OPENROUTER_MODEL` | Идентификатор модели в API провайдера |

**API и дашборд:**

| Переменная | Описание |
|------------|----------|
| `DATABASE_URL` | SQLite по умолчанию: `sqlite:///data/documents.sqlite3` |
| `DECAY_HALF_LIFE_DAYS` | Полураспад веса документов в агрегатах (по умолчанию `90`) |
| `CORS_ORIGINS` | Origins для браузерного доступа к API |

Параметры дашборда в query API: `process_group` (`catalog` \| `macro` \| `meso` \| `free`), `actor_group` (`original` \| `meso` \| `macro`); для строк вне каталога в drilldown используйте `process_key` из ответа (приоритет над `process_id`). Детали — в Swagger.

## Тесты

Смоук-тесты API без вызова LLM и без внешней сети:

```bash
PYTHONPATH=. python3 -m pytest tests/test_api_smoke.py -v
```

Используется отдельный файл БД `data/test_api_smoke.sqlite3`.
