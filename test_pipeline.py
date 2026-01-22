"""
Тестовый скрипт для проверки пайплайна
"""
from pathlib import Path
from pipeline import DocumentPipeline
from config import DATA_DIR, OUTPUT_DIR
import json


def test_single_document():
    """Тестирует обработку одного документа"""
    print("=" * 60)
    print("ТЕСТ: Обработка одного документа")
    print("=" * 60)
    
    # Находим первый доступный документ
    test_files = list(DATA_DIR.glob("*.docx")) + list(DATA_DIR.glob("*.pdf")) + list(DATA_DIR.glob("*.txt"))
    
    if not test_files:
        print("Не найдено тестовых файлов в validate_data/")
        return
    
    test_file = test_files[0]
    print(f"Тестовый файл: {test_file.name}")
    
    try:
        pipeline = DocumentPipeline()
        result = pipeline.process_document(test_file)
        
        print("\nРЕЗУЛЬТАТЫ:")
        print(f"Сущностей: {result['statistics']['total_entities']}")
        print(f"Связей: {result['statistics']['total_relations']}")
        print(f"Цепочек: {result['statistics']['total_chains']}")
        print(f"\nБизнес-процесс: {result['business_process']['category']}")
        print(f"Подпроцесс: {result['business_process']['subprocess']}")
        print(f"Уверенность: {result['business_process']['confidence']:.2f}")
        
        print("\nПримеры сущностей:")
        for entity in result['entities'][:5]:
            print(f"  - {entity['text']} ({entity['type']})")
        
        print("\nПримеры связей:")
        for rel in result['relations'][:3]:
            print(f"  - {rel['source']} --[{rel['relation']}]--> {rel['target']}")
        
        print("\nПримеры цепочек:")
        for chain in result['relation_chains'][:3]:
            print(f"  - {' -> '.join(chain)}")
        
        # Сохраняем результат
        output_file = OUTPUT_DIR / f"test_{test_file.stem}_result.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\nПолный результат сохранен в: {output_file}")
        
    except Exception as e:
        print(f"ОШИБКА: {str(e)}")
        import traceback
        traceback.print_exc()


def test_text_extraction():
    """Тестирует извлечение текста из документов"""
    print("\n" + "=" * 60)
    print("ТЕСТ: Извлечение текста из документов")
    print("=" * 60)
    
    from document_reader import DocumentReader
    
    reader = DocumentReader()
    test_files = list(DATA_DIR.glob("*.docx"))[:1] + list(DATA_DIR.glob("*.pdf"))[:1]
    
    for test_file in test_files:
        try:
            text = reader.read_document(test_file)
            print(f"\n{test_file.name}:")
            print(f"  Длина текста: {len(text)} символов")
            print(f"  Первые 200 символов: {text[:200]}...")
        except Exception as e:
            print(f"  ОШИБКА: {str(e)}")


if __name__ == "__main__":
    print("Запуск тестов пайплайна...\n")
    
    # Тест извлечения текста
    test_text_extraction()
    
    # Тест полного пайплайна
    test_single_document()
    
    print("\n" + "=" * 60)
    print("Тесты завершены")
    print("=" * 60)
