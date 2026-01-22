"""
Главный скрипт для запуска пайплайна обработки документов
"""
import argparse
from pathlib import Path
from pipeline import DocumentPipeline
from config import DATA_DIR, OUTPUT_DIR


def main():
    parser = argparse.ArgumentParser(description='Обработка документов для извлечения сущностей, связей и классификации')
    parser.add_argument('--file', type=str, help='Путь к файлу для обработки')
    parser.add_argument('--dir', type=str, help='Директория с файлами для обработки')
    parser.add_argument('--output', type=str, help='Директория для сохранения результатов (по умолчанию: output/)')
    
    args = parser.parse_args()
    
    # Инициализируем пайплайн
    print("Инициализация пайплайна...")
    pipeline = DocumentPipeline()
    
    # Определяем выходную директорию
    output_dir = Path(args.output) if args.output else OUTPUT_DIR
    output_dir.mkdir(exist_ok=True)
    
    files_to_process = []
    
    if args.file:
        # Обрабатываем один файл
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Ошибка: файл не найден: {file_path}")
            return
        files_to_process = [file_path]
    elif args.dir:
        # Обрабатываем все файлы в директории
        dir_path = Path(args.dir)
        if not dir_path.exists():
            print(f"Ошибка: директория не найдена: {dir_path}")
            return
        files_to_process = list(dir_path.glob("*.docx")) + \
                          list(dir_path.glob("*.pdf")) + \
                          list(dir_path.glob("*.txt"))
    else:
        # Обрабатываем все файлы в validate_data
        files_to_process = list(DATA_DIR.glob("*.docx")) + \
                          list(DATA_DIR.glob("*.pdf")) + \
                          list(DATA_DIR.glob("*.txt"))
    
    if not files_to_process:
        print("Не найдено файлов для обработки")
        return
    
    print(f"Найдено файлов для обработки: {len(files_to_process)}")
    
    # Обрабатываем каждый файл
    for i, file_path in enumerate(files_to_process, 1):
        print(f"\n[{i}/{len(files_to_process)}] Обработка: {file_path.name}")
        try:
            result = pipeline.process_and_save(
                file_path,
                output_path=output_dir / f"{file_path.stem}_result.json"
            )
            
            print(f"  ✓ Сущностей найдено: {result['statistics']['total_entities']}")
            print(f"  ✓ Связей найдено: {result['statistics']['total_relations']}")
            print(f"  ✓ Цепочек построено: {result['statistics']['total_chains']}")
            print(f"  ✓ Бизнес-процесс: {result['business_process']['category']} - {result['business_process']['subprocess']}")
            print(f"  ✓ Результат сохранен: {output_dir / f'{file_path.stem}_result.json'}")
            
        except Exception as e:
            print(f"  ✗ Ошибка при обработке: {str(e)}")
            import traceback
            traceback.print_exc()
    
    print(f"\nОбработка завершена. Результаты сохранены в: {output_dir}")


if __name__ == "__main__":
    main()
