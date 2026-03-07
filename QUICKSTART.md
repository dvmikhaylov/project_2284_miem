# Быстрый старт

## Установка

```bash
pip install -r requirements.txt
```

Опционально (для baseline при использовании SpaCy вместо Natasha):
```bash
python -m spacy download ru_core_news_md
```

## Запуск

Два подхода: **baseline** и **OpenRouter**.

### Baseline (без API-ключей)
```bash
python run.py --baseline
python run.py --baseline --file validate_data/Договор.docx
python run.py --baseline --dir validate_data --output output/baseline
```

Или напрямую:
```bash
python -m baseline.main --dir validate_data --output output/baseline
```

### OpenRouter (один вызов LLM на документ)
Ключ в `key.sh`: `export OPENROUTER_API_KEY=sk-or-...`
```bash
source key.sh
python run.py --openrouter
python run.py --openrouter --file validate_data/Договор.docx --output output/exp_llama_relations
```

Или напрямую:
```bash
source key.sh
python -m experiments.exp_llama_relations.run --dir validate_data
```

### Оба подхода разом
```bash
source key.sh
python -m experiments.run_all
```

## Результаты

- **Baseline:** `output/baseline/<имя_файла>_result.json`
- **OpenRouter:** `output/exp_llama_relations/<имя_файла>_result.json`

В каждом JSON: сущности (entities), связи (relations), цепочки (relation_chains), бизнес-процесс (business_process), статистика.

## Настройка

- **Baseline:** `baseline/config.py` (NER, GPU, чанки, путь к бизнес-процессам).
- **OpenRouter:** `baseline_with_llama_and_rubert/config.py` (OPENROUTER_MODEL, таймаут, ретраи). Промпт: `baseline_with_llama_and_rubert/unified_openrouter.py` → `_build_unified_prompt`.
