# OpenRouter + fallback (baseline_with_llama_and_rubert)

Основной режим: **один вызов OpenRouter на документ** (unified) — NER, связи и бизнес-процесс в одном ответе LLM. Модель по умолчанию — **платная** `openai/gpt-4o`.

При отсутствии ключа или пустом ответе API используется fallback: NER (Natasha/OpenRouter по шагам) → связи (паттерны/OpenRouter) → классификация RuBERT.

## Запуск

Из корня проекта (ключ в `key.sh`):

```bash
source key.sh
python -m experiments.exp_llama_relations.run
python -m experiments.exp_llama_relations.run --file validate_data/Договор.docx --output output/exp_llama_relations
```

Или через обёртку папки (тот же пайплайн с --file/--dir):

```bash
source key.sh
python -m baseline_with_llama_and_rubert.run --dir validate_data
```

## Настройка (config.py)

- **OPENROUTER_API_KEY** — ключ OpenRouter (env или key.sh).
- **OPENROUTER_MODEL** — модель (по умолчанию `openai/gpt-4o`). Варианты: `openai/gpt-oss-120b:free`, `anthropic/claude-3.5-sonnet` и др.
- **OPENROUTER_TIMEOUT**, **OPENROUTER_RETRIES**, **OPENROUTER_RETRY_DELAY** — таймаут и ретраи.

## Промпт

Текст промпта задаётся в `unified_openrouter.py`, функция `_build_unified_prompt(text)`. Лог промптов и ответов: `output/prompts_unified.log`.

## Этапы (unified)

1. Чтение документа (baseline `DocumentReader`).
2. Один запрос к OpenRouter: сущности (PER, ORG, LOC), связи, бизнес-процесс из списка.
3. Парсинг JSON, сбор цепочек, сохранение результата.

Fallback (если unified вернул пусто): пошагово NER → связи → RuBERT (как в старом эксперименте).
