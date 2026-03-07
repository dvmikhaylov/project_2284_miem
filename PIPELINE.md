# Пайплайн: как всё устроено

Подробное описание двух подходов, потока данных и файлов — чтобы быстро вникать в проект.

---

## Два подхода в проекте

| Подход | Суть | Точка входа | Результаты |
|--------|------|--------------|------------|
| **Baseline** | NER (Natasha), связи по паттернам, бизнес-процесс по ключевым словам | `python -m baseline.main` или `python run.py --baseline` | `output/baseline/*.json` |
| **OpenRouter** | Один вызов LLM на документ: NER + цепочки + бизнес-процесс в одном ответе | `python -m experiments.exp_llama_relations.run` или `python run.py --openrouter` | `output/exp_llama_relations/*.json` |

Ниже — по шагам для каждого подхода.

---

## 1. Baseline-пайплайн

### Схема

```
Файл (PDF/DOCX/TXT)
    → DocumentReader.read_document()     [baseline/document_reader.py]
    → текст
    → разбиение на чанки (CHUNK_SIZE)    [baseline/pipeline.py: _chunk_text]
    → для каждого чанка:
        → NERExtractor.extract()         [baseline/ner_extractor.py]  — Natasha (или fallback по regex)
        → RelationExtractor.extract()    [baseline/relation_extractor.py] — паттерны по тексту
    → объединение сущностей по документам (дедупликация по нормализованному тексту)
    → ProcessClassifier.classify()       [baseline/process_classifier.py] — по ключевым словам из business_processes
    → сбор цепочек из сущностей и связей [baseline/pipeline.py: _build_relation_chains]
    → JSON на диск
```

### Ключевые файлы

- **`baseline/main.py`** — парсит аргументы (--file, --dir, --output), вызывает `DocumentPipeline`, пишет JSON.
- **`baseline/pipeline.py`** — класс `DocumentPipeline`: чтение, чанки, NER, связи, классификация, цепочки, сохранение.
- **`baseline/document_reader.py`** — чтение PDF (pymupdf), DOCX (python-docx), TXT.
- **`baseline/ner_extractor.py`** — Natasha (PER, ORG, LOC) или regex-fallback.
- **`baseline/relation_extractor.py`** — поиск связей по паттернам в тексте.
- **`baseline/process_classifier.py`** — сопоставление текста со списком бизнес-процессов по ключевым словам.
- **`baseline/config.py`** — DATA_DIR, OUTPUT_DIR, NER_MODEL, CHUNK_SIZE, MAX_TEXT_LENGTH, путь к бизнес-процессам.

### Конфиг и данные

- Данные по умолчанию: **`validate_data/`**.
- Справочник процессов: **`baseline/config.py`** → `BUSINESS_PROCESSES_FILE` (например `business_processes/business_processes.json` или .txt).
- Вывод: **`output/baseline/<имя_файла>_result.json`**.

---

## 2. OpenRouter-пайплайн (один вызов LLM)

### Схема

```
Файл (PDF/DOCX/TXT)
    → DocumentReader.read_document()     [baseline/document_reader.py]
    → текст (до MAX_DOC_CHARS символов)   [unified_openrouter.py]
    → один запрос в OpenRouter:
        → промпт = _build_unified_prompt(text)   [unified_openrouter.py]
        → в промпте: инструкция по сущностям (типы, акторы), цепочкам, бизнес-процессу + список процессов + текст
        → call_openrouter(prompt)                [openrouter_client.py]
    → ответ модели (сырой JSON-строка)
    → _parse_unified_response(raw)       [unified_openrouter.py]
        → entities, relations (или из relation_chains), relation_chains, business_process
    → _normalize_entities()              — проверка типов, сохранение actor_* для акторов
    → дедупликация сущностей по тексту
    → сопоставление source/target связей с сущностями из списка → relations_list
    → цепочки: либо из ответа (relation_chains), либо собрать из relations_list
    → _match_business_process(bp_raw)    — подстановка в справочник процессов
    → JSON: entities, relations, relation_chains, business_process, statistics
    → сохранение в output/exp_llama_relations/
```

Если **нет ключа OpenRouter** или **ответ пустой** после ретрая:

- Запускается **fallback**: тот же текст идёт в пошаговый пайплайн (чанки → NER из `extract_entities.ner` → связи из `extract_relations_llama.relations` → классификация RuBERT из `classify_rubert.classifier`), результат в том же формате.

### Ключевые файлы

- **`experiments/exp_llama_relations/run.py`** — точка входа: сбор файлов (--file / --dir), для каждого файла чтение → `process_document(fp)` → сохранение JSON.
- **`baseline_with_llama_and_rubert/unified_openrouter.py`** — ядро OpenRouter-режима:
  - **`_build_unified_prompt(text)`** — собирает промпт (типы сущностей, таксономия акторов, правила цепочек, список бизнес-процессов, текст документа).
  - **`process_document_unified(text)`** — вызов API, парсинг, нормализация сущностей, сбор связей и цепочек, бизнес-процесс.
  - **`_parse_unified_response(raw)`** — из сырого ответа достаёт entities, relations (или строит из relation_chains), relation_chains, business_process.
  - **`_normalize_entities()`** — допустимые типы (PERSON, ORG, DEPARTMENT, POSITION, SYSTEM, DOC_TYPE, LOCATION, DATE, TASK_ACTION, ISSUE_PROBLEM), для акторов сохраняются actor_category, actor_subcategory, role_in_process, is_internal.
  - **`_match_business_process(bp_raw)`** — сопоставление ответа модели со справочником процессов.
- **`baseline_with_llama_and_rubert/openrouter_client.py`** — `call_openrouter(prompt, api_key, model, max_tokens, temperature, timeout, max_retries, retry_delay)`: POST в OpenRouter, ретрай при 429/таймауте/пустом ответе.
- **`baseline_with_llama_and_rubert/config.py`** — OPENROUTER_API_KEY, OPENROUTER_MODEL, OPENROUTER_TIMEOUT, OPENROUTER_RETRIES, OPENROUTER_RETRY_DELAY, BUSINESS_PROCESSES_JSON, пути.

### Конфиг и данные

- Ключ: **`OPENROUTER_API_KEY`** (env или `source key.sh`).
- Модель: **`OPENROUTER_MODEL`** (по умолчанию `openai/gpt-4o`).
- Таймаут/ретраи: OPENROUTER_TIMEOUT (300), OPENROUTER_RETRIES (1), OPENROUTER_RETRY_DELAY (10).
- Справочник процессов: **`business_processes/business_processes.json`** (подставляется в промпт и в _match_business_process).
- Лог промптов и ответов: **`output/prompts_unified.log`** (дозапись при каждом вызове).
- Вывод: **`output/exp_llama_relations/<имя_файла>_result.json`**.

### Fallback (когда OpenRouter не используется или не ответил)

- **`baseline_with_llama_and_rubert/extract_entities/ner.py`** — NER: при наличии ключа OpenRouter — запрос к API по чанкам; иначе Natasha или regex.
- **`baseline_with_llama_and_rubert/extract_relations_llama/relations.py`** — связи: при наличии ключа OpenRouter — API; иначе локальный LLM (если есть) или паттерны + proximity.
- **`baseline_with_llama_and_rubert/classify_rubert/classifier.py`** — zero-shot классификация текста в бизнес-процессы (RuBERT).

---

## 3. Формат результата (общий для обоих подходов)

Каждый документ → один JSON-файл. Пример структуры:

```json
{
  "document": "имя_файла.pdf",
  "entities": [
    {
      "id": 0,
      "text": "АО «ВДНХ»",
      "type": "ORG",
      "actor_category": "INTERNAL",
      "actor_subcategory": "UNKNOWN_INTERNAL_ORG",
      "role_in_process": "UNKNOWN_ROLE",
      "is_internal": true
    }
  ],
  "relations": [
    {
      "source": "Сыч Е.А.",
      "target": "лист согласования",
      "relation": "подписать_документ",
      "source_type": "PERSON",
      "target_type": "DOC_TYPE",
      "context": ""
    }
  ],
  "relation_chains": [
    ["Сыч Е.А.", "подписать_документ", "лист согласования"]
  ],
  "business_process": {
    "category": "Юридические и комплаенс",
    "subprocess": "Договорная работа",
    "number": 0,
    "confidence": 0.9,
    "alternatives": []
  },
  "statistics": {
    "total_entities": 10,
    "total_relations": 5,
    "total_chains": 5,
    "text_length": 5000
  }
}
```

- **OpenRouter** может отдавать все типы сущностей и поля акторов (см. выше).
- **Baseline** обычно даёт только type: PER/ORG/LOC и не заполняет actor_*.

---

## 4. Как запускать

```bash
# Из корня проекта

# Baseline (без ключей)
python run.py --baseline
python run.py --baseline --file validate_data/Договор.docx --output output/baseline

# OpenRouter (нужен source key.sh)
source key.sh
python run.py --openrouter
python run.py --openrouter --dir validate_data --output output/exp_llama_relations

# Оба подхода подряд на validate_data
python -m experiments.run_all
```

Прямой вызов модулей:

```bash
python -m baseline.main --dir validate_data --output output/baseline
python -m experiments.exp_llama_relations.run --dir validate_data
```

---

## 5. Где что править

| Задача | Файл / место |
|--------|-------------------------------|
| Промпт OpenRouter (сущности, цепочки, процессы) | `baseline_with_llama_and_rubert/unified_openrouter.py` → функция `_build_unified_prompt` |
| Модель, таймаут, ретраи OpenRouter | `baseline_with_llama_and_rubert/config.py` |
| Логика парсинга ответа LLM | `unified_openrouter.py` → `_parse_unified_response`, `_normalize_entities` |
| Список бизнес-процессов | `business_processes/business_processes.json` |
| Чтение документов (PDF/DOCX) | `baseline/document_reader.py` |
| Baseline: NER, связи, классификация | `baseline/ner_extractor.py`, `relation_extractor.py`, `process_classifier.py` |
| Fallback NER/связи/RuBERT | `extract_entities/ner.py`, `extract_relations_llama/relations.py`, `classify_rubert/classifier.py` |

---

## 6. Краткая схема потока (OpenRouter)

```
run.py (exp_llama_relations)
  → для каждого файла: DocumentReader.read_document(path) → text
  → process_document(path):
       → process_document_unified(text)
            → _build_unified_prompt(text)  → prompt
            → call_openrouter(prompt)       → raw
            → log_prompt_and_response(prompt, raw)
            → _parse_unified_response(raw) → entities, relations, relation_chains, bp
            → _normalize_entities(entities, text)
            → дедупликация сущностей, сбор relations_list по entity_texts
            → цепочки из relation_chains или из relations_list
            → _match_business_process(bp)  → business_process
            → return { entities, relations, relation_chains, business_process, statistics }
       → если None: fallback по чанкам (extract_entities, extract_relations, classify_zero_shot)
  → save_result(result, output_dir, stem)  → JSON на диск
```

Этого достаточно, чтобы ориентироваться в коде и дорабатывать пайплайн.
