"""
Тестовый скрипт для baseline-пайплайна
"""
from pathlib import Path
import json

from .pipeline import DocumentPipeline
from .config import DATA_DIR, OUTPUT_DIR
from .document_reader import DocumentReader


def test_text_extraction():
    print("=" * 60)
    print("ТЕСТ: Извлечение текста")
    print("=" * 60)
    reader = DocumentReader()
    test_files = list(DATA_DIR.glob("*.docx"))[:1] + list(DATA_DIR.glob("*.pdf"))[:1]
    for test_file in test_files:
        try:
            text = reader.read_document(test_file)
            print(f"\n{test_file.name}: {len(text)} символов")
            print(f"  {text[:200]}...")
        except Exception as e:
            print(f"  ОШИБКА: {e}")


def test_single_document():
    print("\n" + "=" * 60)
    print("ТЕСТ: Обработка одного документа")
    print("=" * 60)
    test_files = list(DATA_DIR.glob("*.docx")) + list(DATA_DIR.glob("*.pdf")) + list(DATA_DIR.glob("*.txt"))
    if not test_files:
        print("Нет файлов в validate_data/")
        return
    test_file = test_files[0]
    print(f"Файл: {test_file.name}")
    try:
        pipeline = DocumentPipeline()
        result = pipeline.process_document(test_file)
        print(f"Сущностей: {result['statistics']['total_entities']}")
        print(f"Связей: {result['statistics']['total_relations']}")
        print(f"Бизнес-процесс: {result['business_process']['category']} - {result['business_process']['subprocess']}")
        out = OUTPUT_DIR / f"test_{test_file.stem}_result.json"
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"Сохранено: {out}")
    except Exception as e:
        print(f"ОШИБКА: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_text_extraction()
    test_single_document()
    print("\nТесты завершены.")
