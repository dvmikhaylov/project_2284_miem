"""
CLI: OpenRouter-пайплайн для одного файла или директории.

  python -m openrouter_pipeline.run [--file PATH] [--dir PATH] [--output DIR]
"""
import argparse
import json
from pathlib import Path

from .config import DATA_DIR, OPENROUTER_API_KEY, OPENROUTER_MODEL, PROJECT_ROOT
from .document_reader import DocumentReader
from .unified_openrouter import process_document_unified

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output" / "openrouter"


def save_result(result: dict, output_dir: Path, stem: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{stem}_result.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return out_file


def _collect_files(args) -> list:
    if args.file:
        p = Path(args.file)
        return [p] if p.exists() else []
    if args.dir:
        d = Path(args.dir)
        if not d.exists():
            return []
        return list(d.glob("*.docx")) + list(d.glob("*.pdf")) + list(d.glob("*.txt"))
    return list(DATA_DIR.glob("*.docx")) + list(DATA_DIR.glob("*.pdf")) + list(DATA_DIR.glob("*.txt"))


def process_document(file_path: Path) -> dict:
    text = DocumentReader().read_document(file_path)
    if not text or not text.strip():
        return {"error": "Пустой документ", "document": str(file_path.name)}
    if not OPENROUTER_API_KEY:
        return {"error": "Задайте OPENROUTER_API_KEY (например: source key.sh)", "document": str(file_path.name)}
    result = process_document_unified(text)
    if result is None:
        return {"error": "OpenRouter не вернул результат (см. output/prompts_unified.log)", "document": str(file_path.name)}
    result["document"] = str(file_path.name)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="OpenRouter: извлечение сущностей, связей и бизнес-процессов из документов"
    )
    parser.add_argument("--file", type=str, help="Путь к одному файлу")
    parser.add_argument("--dir", type=str, help="Директория с документами")
    parser.add_argument("--output", type=str, default=None, help="Директория для результатов")
    args = parser.parse_args()

    output_dir = Path(args.output) if args.output else DEFAULT_OUTPUT_DIR
    files = _collect_files(args)
    if not files:
        print("Нет файлов. Укажите --file или --dir или положите документы в validate_data/")
        return

    print(
        "OpenRouter: проход 1 — извлечение; проход 2 — нормализация графа (OPENROUTER_SECOND_PASS=0 отключает)"
    )
    print(f"  Модель: {OPENROUTER_MODEL}")
    print(f"  Файлов: {len(files)}, результаты: {output_dir}\n")

    for i, fp in enumerate(files, 1):
        print(f"[{i}/{len(files)}] {fp.name}")
        try:
            result = process_document(fp)
            out = save_result(result, output_dir, fp.stem)
            if "error" in result:
                print(f"  ✗ {result['error']}")
            else:
                sp = result.get("statistics", {}).get("second_pass_applied")
                sp_note = f", 2-й проход: {'да' if sp else 'нет'}" if sp is not None else ""
                print(
                    f"  ✓ Сущностей: {result['statistics']['total_entities']}, "
                    f"связей: {result['statistics']['total_relations']}{sp_note}"
                )
                bps = result.get("business_processes") or []
                if bps:
                    top = bps[0]
                    print(
                        f"  ✓ Процессы: {len(bps)} (главный: {top.get('category')} — "
                        f"{top.get('subprocess')}, priority={top.get('priority')}, "
                        f"relevance={top.get('relevance')})"
                    )
                else:
                    bp = result.get("business_process") or {}
                    print(f"  ✓ Бизнес-процесс: {bp.get('category')} — {bp.get('subprocess')}")
                print(f"  ✓ {out}")
        except Exception as e:
            print(f"  ✗ {e}")
            import traceback

            traceback.print_exc()
    print(f"\nРезультаты: {output_dir}")


if __name__ == "__main__":
    main()

