"""
Главный скрипт для запуска baseline-пайплайна
"""
import argparse
from pathlib import Path

from .pipeline import DocumentPipeline
from .config import DATA_DIR, OUTPUT_DIR


def main():
    parser = argparse.ArgumentParser(description='Baseline: обработка документов (NER, связи, классификация по ключевым словам)')
    parser.add_argument('--file', type=str, help='Путь к файлу')
    parser.add_argument('--dir', type=str, help='Директория с файлами')
    parser.add_argument('--output', type=str, help='Директория для результатов')
    args = parser.parse_args()
    
    print("Инициализация baseline-пайплайна...")
    pipeline = DocumentPipeline()
    output_dir = Path(args.output) if args.output else OUTPUT_DIR
    output_dir.mkdir(exist_ok=True)
    
    files_to_process = []
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Ошибка: файл не найден: {file_path}")
            return
        files_to_process = [file_path]
    elif args.dir:
        dir_path = Path(args.dir)
        if not dir_path.exists():
            print(f"Ошибка: директория не найдена: {dir_path}")
            return
        files_to_process = list(dir_path.glob("*.docx")) + list(dir_path.glob("*.pdf")) + list(dir_path.glob("*.txt"))
    else:
        files_to_process = list(DATA_DIR.glob("*.docx")) + list(DATA_DIR.glob("*.pdf")) + list(DATA_DIR.glob("*.txt"))
    
    if not files_to_process:
        print("Не найдено файлов для обработки")
        return
    
    print(f"Найдено файлов: {len(files_to_process)}")
    for i, file_path in enumerate(files_to_process, 1):
        print(f"\n[{i}/{len(files_to_process)}] {file_path.name}")
        try:
            result = pipeline.process_and_save(file_path, output_path=output_dir / f"{file_path.stem}_result.json")
            print(f"  ✓ Сущностей: {result['statistics']['total_entities']}, связей: {result['statistics']['total_relations']}")
            print(f"  ✓ Бизнес-процесс: {result['business_process']['category']} - {result['business_process']['subprocess']}")
        except Exception as e:
            print(f"  ✗ Ошибка: {e}")
            import traceback
            traceback.print_exc()
    print(f"\nРезультаты: {output_dir}")


if __name__ == "__main__":
    main()
