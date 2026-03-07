"""Общая логика: два тестовых документа, чтение, чанки, цепочки, сохранение."""
import re
import json
from pathlib import Path
from typing import List, Dict, Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "validate_data"
MAX_TEXT_LENGTH = 10000
CHUNK_SIZE = 2000

TWO_DOCS = [
    PROJECT_ROOT / "validate_data" / "Договор.docx",
    PROJECT_ROOT / "validate_data" / "07_11_2023_СЗ_3264_23_Сыч_Е_А_Виленский_И_Б_ (1).pdf",
]

_ner_extractor = None


def _ner_fallback(text: str) -> List[Dict]:
    """Простой NER по заглавным и АО/ООО/Департамент (если Natasha недоступна)."""
    out, seen = [], set()
    for m in re.finditer(
        r"(?:АО|ООО|ПАО|ИП|Департамент|Департамента)\s*[«\"]?[\w\s]+[»\"]?|(?:[А-ЯЁ][а-яё]+\s+)+[А-ЯЁ][а-яё]+|[А-ЯЁ]\.[А-ЯЁ]\.[А-ЯЁа-яё]+",
        text,
    ):
        t = m.group(0).strip()
        if len(t) < 2 or t.lower() in seen:
            continue
        seen.add(t.lower())
        typ = "ORG" if re.match(r"^(АО|ООО|ПАО|ИП|Департамент)", t) else "PER"
        out.append({"text": t, "type": typ, "start": m.start(), "end": m.end()})
    return out


def get_ner() -> Callable[[str], List[Dict]]:
    """Natasha из baseline, при ошибке — fallback."""
    global _ner_extractor
    if _ner_extractor is not None:
        return _ner_extractor
    try:
        from baseline.ner_extractor import NERExtractor
        _ner = NERExtractor(model_type="natasha", use_gpu=False)
        _ner_extractor = lambda t: _ner.extract(t)
        return _ner_extractor
    except Exception:
        _ner_extractor = _ner_fallback
        return _ner_extractor


def chunk_text(text: str) -> list:
    if len(text) <= MAX_TEXT_LENGTH:
        return [text]
    chunks, cur, cur_len = [], [], 0
    for w in text.split():
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
    rel_by_source = {}
    for r in relations:
        rel_by_source.setdefault(r["source"], []).append(r)
    chains = []
    for e in entities:
        t = e.get("text", e) if isinstance(e, dict) else e
        for r in rel_by_source.get(t, []):
            chains.append([t, r["relation"], r["target"]])
    return chains


def save_result(result: dict, output_dir: Path, stem: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{stem}_result.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return out_file
