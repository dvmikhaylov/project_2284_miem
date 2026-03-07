# Пайплайн извлечения информации из документов (ВДНХ)

Извлечение сущностей (PER, ORG, LOC), связей между ними и классификация документов в бизнес-процессы. Два подхода: **baseline** и **OpenRouter (LLM)**.

## Два подхода

| Подход | Описание | Результаты |
|--------|----------|------------|
| **Baseline** | NER (Natasha), связи по паттернам, классификация по ключевым словам | `output/baseline/` |
| **OpenRouter** | Один вызов LLM на документ: NER + связи + бизнес-процесс. Модель по умолчанию платная (gpt-4o) | `output/exp_llama_relations/` |

## Быстрый старт

```bash
# Установка
pip install -r requirements.txt

# Baseline (без ключей)
python run.py --baseline
python run.py --baseline --file validate_data/Договор.docx
python run.py --baseline --dir validate_data --output output/baseline

# OpenRouter (нужен ключ: source key.sh)
python run.py --openrouter
python run.py --openrouter --file validate_data/Договор.docx --output output/exp_llama_relations
```

Или напрямую:
```bash
python -m baseline.main --dir validate_data --output output/baseline
source key.sh && python -m experiments.exp_llama_relations.run --dir validate_data
```

## Структура проекта

- **`run.py`** — единая точка входа: `--baseline` или `--openrouter`, опции `--file`, `--dir`, `--output`.
- **`baseline/`** — baseline-пайплайн: чтение документов, NER (Natasha), связи по паттернам, классификация по ключевым словам. Конфиг: `baseline/config.py`.
- **`baseline_with_llama_and_rubert/`** — OpenRouter (unified LLM), fallback NER/связи/RuBERT. Промпт и логика в `unified_openrouter.py`, конфиг в `config.py`.
- **`experiments/exp_llama_relations/`** — запуск OpenRouter-пайплайна на файлах (поддержка `--file`, `--dir`, `--output`).
- **`experiments/run_all.py`** — последовательный запуск baseline и OpenRouter на `validate_data/`.
- **`validate_data/`** — тестовые документы (DOCX, PDF, TXT).
- **`business_processes/business_processes.json`** — список бизнес-процессов для классификации.

## Этапы пайплайна (общие)

1. **Чтение документа** — PDF, DOCX, TXT.
2. **NER** — извлечение сущностей: персоны (PER), организации (ORG), локации (LOC).
3. **Связи** — связи между сущностями (кто с кем, тип связи).
4. **Цепочки** — цепочки вида [сущность, связь, сущность].
5. **Бизнес-процесс** — отнесение документа к одному процессу из справочника.

## OpenRouter: настройка

- Ключ: [openrouter.ai/keys](https://openrouter.ai/keys) → сохранить в `key.sh`: `export OPENROUTER_API_KEY=sk-or-...`
- Модель по умолчанию: **платная** `openai/gpt-4o`. Задать другую: `OPENROUTER_MODEL=openai/gpt-oss-120b:free` (бесплатная) или любая модель из каталога OpenRouter.
- Таймаут 300 с, один ретрай при 429/таймауте. Промпт настраивается в `baseline_with_llama_and_rubert/unified_openrouter.py` (функция `_build_unified_prompt`).
- Лог промптов и ответов: `output/prompts_unified.log`.

## Формат результата (JSON)

Для каждого документа сохраняется JSON:

- `document` — имя файла
- `entities` — список сущностей с полями `text`, `type` (PER/ORG/LOC), `id`
- `relations` — список связей: `source`, `target`, `relation`, `source_type`, `target_type`, `context`
- `relation_chains` — цепочки вида `[источник, связь, цель]`
- `business_process` — `category`, `subprocess`, `number`, `confidence`, `alternatives`
- `statistics` — количество сущностей, связей, цепочек, длина текста

## Требования

- Python 3.9+
- Зависимости: `requirements.txt` (в т.ч. pymupdf, python-docx, natasha, transformers, torch для baseline и fallback OpenRouter).
