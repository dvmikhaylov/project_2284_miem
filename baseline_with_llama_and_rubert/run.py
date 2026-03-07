"""
Обёртка эксперимента baseline_with_llama_and_rubert.

Запуск всех этапов по порядку:
  1. read_documents  — чтение PDF/DOCX/TXT
  2. extract_entities — NER (Natasha)
  3. extract_relations_llama — связи (LLM llama.cpp или паттерны)
  4. classify_rubert — zero-shot классификация в бизнес-процессы (RuBERT)

Использование:
  python -m baseline_with_llama_and_rubert.run --file path/to/doc.pdf
  python -m baseline_with_llama_and_rubert.run --dir validate_data
  python -m baseline_with_llama_and_rubert.run --output output/
"""
import argparse
import json
from pathlib import Path

from .config import DATA_DIR, OUTPUT_DIR, MAX_TEXT_LENGTH, CHUNK_SIZE
from .read_documents.reader import read_document
from .extract_entities.ner import extract_entities
from .extract_relations_llama.relations import extract_relations
from .classify_rubert.classifier import classify_zero_shot


def chunk_text(text: str) -> list:
    if len(text) <= MAX_TEXT_LENGTH:
        return [text]
    chunks = []
    words = text.split()
    cur, cur_len = [], 0
    for w in words:
        L = len(w) + 1
        if cur_len + L > CHUNK_SIZE:
            if cur:
                chunks.append(" ".join(cur))
            cur, cur_len = [w], L
        else:
            cur.append(w)
            cur_len += L
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def build_chains(entities: list, relations: list) -> list:
    chains = []
    rel_by_source = {}
    for r in relations:
        rel_by_source.setdefault(r["source"], []).append(r)
    for e in entities:
        t = e["text"]
        for r in rel_by_source.get(t, []):
            chains.append([t, r["relation"], r["target"]])
    return chains


def process_document(file_path: Path) -> dict:
    # 1. Чтение
    text = read_document(file_path)
    if not text or not text.strip():
        return {"error": "Пустой документ", "document": str(file_path.name)}
    
    # 2. NER по чанкам
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
    
    # 3. Связи (LLM или паттерны)
    all_relations = []
    for ch in chunks:
        all_relations.extend(extract_relations(ch, entities_list))
    seen_rel = set()
    relations_list = []
    for r in all_relations:
        k = (r["source"].lower(), r["relation"], r["target"].lower())
        if k not in seen_rel:
            seen_rel.add(k)
            relations_list.append(r)
    
    # 4. Классификация (RuBERT zero-shot)
    classification = classify_zero_shot(text)
    
    chains = build_chains(entities_list, relations_list)
    
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


def main():
    parser = argparse.ArgumentParser(description="Эксперимент: baseline + llama (связи) + rubert (классификация)")
    parser.add_argument("--file", type=str, help="Путь к файлу")
    parser.add_argument("--dir", type=str, help="Директория с файлами")
    parser.add_argument("--output", type=str, default=None, help="Директория для результатов")
    args = parser.parse_args()
    
    out_dir = Path(args.output) if args.output else OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    
    files = []
    if args.file:
        p = Path(args.file)
        if not p.exists():
            print(f"Файл не найден: {p}")
            return
        files = [p]
    elif args.dir:
        d = Path(args.dir)
        if not d.exists():
            print(f"Директория не найдена: {d}")
            return
        files = list(d.glob("*.docx")) + list(d.glob("*.pdf")) + list(d.glob("*.txt"))
    else:
        files = list(DATA_DIR.glob("*.docx")) + list(DATA_DIR.glob("*.pdf")) + list(DATA_DIR.glob("*.txt"))
    
    if not files:
        print("Нет файлов для обработки")
        return
    
    print(f"Эксперимент: baseline_with_llama_and_rubert. Файлов: {len(files)}")
    for i, fp in enumerate(files, 1):
        print(f"\n[{i}/{len(files)}] {fp.name}")
        try:
            result = process_document(fp)
            out_file = out_dir / f"{fp.stem}_result.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            if "error" in result:
                print(f"  ✗ {result['error']}")
            else:
                print(f"  ✓ Сущностей: {result['statistics']['total_entities']}, связей: {result['statistics']['total_relations']}")
                print(f"  ✓ Бизнес-процесс: {result['business_process']['category']} — {result['business_process']['subprocess']}")
                print(f"  ✓ Сохранено: {out_file}")
        except Exception as e:
            print(f"  ✗ Ошибка: {e}")
            import traceback
            traceback.print_exc()
    print(f"\nГотово. Результаты: {out_dir}")


if __name__ == "__main__":
    main()
