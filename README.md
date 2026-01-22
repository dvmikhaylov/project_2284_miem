# Пайплайн извлечения информации из документов

Пайплайн для извлечения именованных сущностей, связей между ними и классификации документов в бизнес-процессы из русскоязычных документов.

## Возможности

- Извлечение именованных сущностей (PER, ORG, LOC) из документов
- Определение связей между сущностями
- Построение цепочек связей (например: ВДНХ -> заключить договор -> ООО ПромТрансНефть)
- Классификация документов в бизнес-процессы из предопределенного списка
- Поддержка форматов: DOCX, PDF, TXT

## Установка

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Установите русскую модель для SpaCy (если используете spacy вместо natasha):
```bash
python -m spacy download ru_core_news_md
```

## Использование

### Обработка одного файла:
```bash
python main.py --file path/to/document.docx
```

### Обработка всех файлов в директории:
```bash
python main.py --dir path/to/documents/
```

### Обработка всех файлов из validate_data:
```bash
python main.py
```

### Указание выходной директории:
```bash
python main.py --file document.docx --output results/
```

## Структура вывода

Результаты сохраняются в JSON формате со следующей структурой:

```json
{
  "document": "название_файла",
  "entities": [
    {
      "text": "ВДНХ",
      "type": "ORG",
      "id": 0
    }
  ],
  "relations": [
    {
      "source": "ВДНХ",
      "target": "ООО ПромТрансНефть",
      "relation": "заключить_договор",
      "source_type": "ORG",
      "target_type": "ORG",
      "context": "ВДНХ заключил договор с ООО ПромТрансНефть"
    }
  ],
  "relation_chains": [
    ["ВДНХ", "заключить_договор", "ООО ПромТрансНефть"]
  ],
  "business_process": {
    "category": "Закупки и административные процессы",
    "subprocess": "Контракты с поставщиками",
    "number": 83,
    "confidence": 0.8,
    "alternatives": [...]
  },
  "statistics": {
    "total_entities": 10,
    "total_relations": 5,
    "total_chains": 5,
    "text_length": 5000
  }
}
```

## Архитектура

- `document_reader.py` - чтение документов различных форматов
- `ner_extractor.py` - извлечение именованных сущностей (Natasha/SpaCy)
- `relation_extractor.py` - извлечение связей между сущностями
- `process_classifier.py` - классификация в бизнес-процессы
- `business_process_loader.py` - загрузка списка бизнес-процессов
- `pipeline.py` - основной пайплайн обработки
- `main.py` - точка входа

## Модели

- **NER**: Natasha (по умолчанию) или ru_core_news_md (SpaCy)
- **Relation Extraction**: Паттерн-подход с возможностью расширения LLM
- **Classification**: Keyword-based классификация с возможностью расширения ML-моделями

## Настройка

Параметры можно изменить в `config.py`:
- `USE_GPU` - использование GPU (MPS на Mac)
- `NER_MODEL` - выбор модели NER ("natasha" или "spacy")
- `MAX_TEXT_LENGTH` - максимальная длина текста
- `CHUNK_SIZE` - размер чанков для обработки
