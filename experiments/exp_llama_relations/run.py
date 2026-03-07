"""
OpenRouter: один вызов LLM на документ — NER, связи и бизнес-процесс в одном ответе.

При наличии OPENROUTER_API_KEY (source key.sh) используется unified_openrouter.
  - Модель по умолчанию: платная (openai/gpt-4o). Задать другую: OPENROUTER_MODEL=...
  - Таймаут: OPENROUTER_TIMEOUT (300 с). Один ретрай при 429/таймауте/пустом ответе.
  - Если ответ пустой — fallback: NER → связи → RuBERT.
Результаты: output/exp_llama_relations/ (entities, relations, relation_chains, business_process).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import experiments._patch_pkg_resources  # noqa: E402

from baseline.document_reader import DocumentReader
from baseline_with_llama_and_rubert.unified_openrouter import process_document_unified
from baseline_with_llama_and_rubert.extract_entities.ner import extract_entities
from baseline_with_llama_and_rubert.extract_relations_llama.relations import extract_relations
from baseline_with_llama_and_rubert.classify_rubert.classifier import classify_zero_shot

from experiments._common import (
    PROJECT_ROOT,
    DATA_DIR,
    chunk_text,
    build_chains,
    save_result,
)

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output" / "exp_llama_relations"


def process_document(file_path: Path) -> dict:
    reader = DocumentReader()
    text = reader.read_document(file_path)
    if not text or not text.strip():
        return {"error": "Пустой документ", "document": str(file_path.name)}

    # Один вызов OpenRouter на весь документ (если ключ задан)
    result = process_document_unified(text)
    if result is not None:
        result["document"] = str(file_path.name)
        return result

    # Fallback: пошаговый пайплайн (NER → связи → RuBERT)
    chunks = chunk_text(text)
    all_entities = []
    for ch in chunks:
        all_entities.extend(extract_entities(ch))
    unique_entities = {}
    for e in all_entities:
        norm = " ".join(e["text"].split())
        key = norm.lower().strip()
        if len(key) < 2:
            continue
        if key not in unique_entities or len(norm) > len(unique_entities[key]["text"]):
            e["text"] = norm
            unique_entities[key] = e
    entities_list = list(unique_entities.values())

    all_relations = []
    for ch in chunks:
        all_relations.extend(extract_relations(ch, entities_list))
    seen = set()
    relations_list = []
    for r in all_relations:
        k = (r["source"].lower(), r["relation"], r["target"].lower())
        if k not in seen:
            seen.add(k)
            relations_list.append(r)

    classification = classify_zero_shot(text)
    chains = build_chains(
        [{"text": e["text"]} for e in entities_list],
        relations_list,
    )

    return {
        "document": str(file_path.name),
        "entities": [{"text": e["text"], "type": e["type"], "id": i} for i, e in enumerate(entities_list)],
        "relations": [
            {
                "source": r["source"],
                "target": r["target"],
                "relation": r["relation"],
                "source_type": r.get("source_type", "UNK"),
                "target_type": r.get("target_type", "UNK"),
                "context": r.get("context", ""),
            }
            for r in relations_list
        ],
        "relation_chains": chains,
        "business_process": {
            "category": classification["category"],
            "subprocess": classification["subprocess"],
            "number": classification["number"],
            "confidence": classification["confidence"],
            "alternatives": classification.get("alternatives", []),
        },
        "statistics": {
            "total_entities": len(entities_list),
            "total_relations": len(relations_list),
            "total_chains": len(chains),
            "text_length": len(text),
        },
    }


def _collect_files(args) -> list:
    """Собирает список файлов из --file, --dir или validate_data."""
    if args.file:
        p = Path(args.file)
        if not p.exists():
            return []
        return [p]
    if args.dir:
        d = Path(args.dir)
        if not d.exists():
            return []
        return list(d.glob("*.docx")) + list(d.glob("*.pdf")) + list(d.glob("*.txt"))
    return list(DATA_DIR.glob("*.docx")) + list(DATA_DIR.glob("*.pdf")) + list(DATA_DIR.glob("*.txt"))


def main():
    parser = argparse.ArgumentParser(description="OpenRouter: NER + связи + бизнес-процесс одним вызовом LLM")
    parser.add_argument("--file", type=str, help="Путь к одному файлу")
    parser.add_argument("--dir", type=str, help="Директория с документами")
    parser.add_argument("--output", type=str, default=None, help="Директория для результатов")
    args = parser.parse_args()

    output_dir = Path(args.output) if args.output else DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    files = _collect_files(args)
    if not files:
        print("Нет файлов для обработки. Укажите --file или --dir или положите документы в validate_data/")
        return

    from baseline_with_llama_and_rubert.config import OPENROUTER_API_KEY, OPENROUTER_MODEL
    if OPENROUTER_API_KEY:
        print("OpenRouter: один вызов LLM на документ (NER + связи + бизнес-процесс)")
        print(f"  Модель: {OPENROUTER_MODEL}")
    else:
        print("OpenRouter: ключ не задан (source key.sh). Используется fallback: NER → связи → RuBERT.")
    print(f"  Файлов: {len(files)}, результаты: {output_dir}\n")

    for i, fp in enumerate(files, 1):
        print(f"[{i}/{len(files)}] {fp.name}")
        try:
            result = process_document(fp)
            out = save_result(result, output_dir, fp.stem)
            if "error" in result:
                print(f"  ✗ {result['error']}")
            else:
                print(f"  ✓ Сущностей: {result['statistics']['total_entities']}, связей: {result['statistics']['total_relations']}")
                print(f"  ✓ Бизнес-процесс: {result['business_process']['category']} — {result['business_process']['subprocess']}")
                print(f"  ✓ {out}")
        except Exception as e:
            print(f"  ✗ {e}")
            import traceback
            traceback.print_exc()
    print(f"\nРезультаты: {output_dir}")


if __name__ == "__main__":
    main()
