"""
Этап 2: извлечение именованных сущностей (NER).
Приоритет: OpenRouter (gpt-oss-120b) → локальная NER_LLAMA → Natasha → fallback.
Промпты в лог: DEBUG_LLM_NER=1 или запись в output/prompts_ner.log
"""
import json
import os
import re
from pathlib import Path
from typing import List, Dict, Optional

_ner_impl = None
_ner_llama_model = None
DEBUG_NER = os.environ.get("DEBUG_LLM_NER", "").strip() in ("1", "true", "yes")


def _ner_openrouter(text: str) -> List[Dict]:
    """NER через OpenRouter (gpt-oss-120b:free)."""
    from ..config import (
        OPENROUTER_API_KEY,
        OPENROUTER_MODEL,
        NER_LLAMA_MAX_TOKENS,
        NER_LLAMA_TEMPERATURE,
    )
    from ..openrouter_client import call_openrouter
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY не задан")
    text_slice = text[:3000]
    prompt = """Извлеки из текста именованные сущности: персоны (PER), организации (ORG), локации (LOC).
Используй только типы PER, ORG, LOC. Ответ — только JSON-массив объектов с полями "text" и "type".
Пример: [{"text": "АО ВДНХ", "type": "ORG"}, {"text": "Иванов И.И.", "type": "PER"}]

Текст:
""" + text_slice + """

Ответ — только массив JSON, без markdown:"""
    raw = call_openrouter(
        prompt,
        api_key=OPENROUTER_API_KEY,
        model=OPENROUTER_MODEL,
        max_tokens=NER_LLAMA_MAX_TOKENS,
        temperature=NER_LLAMA_TEMPERATURE,
    )
    if DEBUG_NER:
        _log_ner_prompt(prompt, raw_response=raw or "", model_path="OpenRouter:" + OPENROUTER_MODEL)
    if not raw:
        return _ner_fallback(text)
    raw = raw.strip()
    if raw.lower().startswith("```"):
        raw = re.sub(r"^```\w*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw)
    start = raw.find("[")
    if start >= 0:
        raw = raw[start:]
    if not raw.rstrip().endswith("]"):
        last = raw.rfind("}")
        if last >= 0:
            raw = raw[: last + 1] + "]"
    entities = _parse_ner_json(raw, text)
    if not entities:
        return _ner_fallback(text)
    return entities


def _log_ner_prompt(prompt: str, raw_response: str = "", model_path: str = ""):
    """Промпты пишутся в output/prompts_ner.log; при DEBUG_LLM_NER=1 — ещё в консоль."""
    from ..config import PROJECT_ROOT
    msg = f"[NER] model={model_path}\n--- prompt ---\n{prompt}\n--- end prompt ---\n"
    if raw_response:
        msg += f"--- response (first 500) ---\n{raw_response[:500]}\n--- end response ---\n"
    if DEBUG_NER:
        print(msg)
    log_file = PROJECT_ROOT / "output" / "prompts_ner.log"
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def _ner_llama(text: str) -> List[Dict]:
    """NER через llama.cpp (Qwen 32B/14B). Извлекает PER, ORG, LOC из текста."""
    from ..config import (
        NER_LLAMA_MODEL_PATH,
        NER_LLAMA_MAX_TOKENS,
        NER_LLAMA_TEMPERATURE,
    )
    if not NER_LLAMA_MODEL_PATH or not Path(NER_LLAMA_MODEL_PATH).exists():
        raise FileNotFoundError("NER_LLAMA_MODEL_PATH не задан или файл не найден")
    try:
        from llama_cpp import Llama
    except ImportError:
        raise RuntimeError("llama-cpp-python не установлен")
    global _ner_llama_model
    if _ner_llama_model is None:
        _ner_llama_model = Llama(
            model_path=str(NER_LLAMA_MODEL_PATH),
            n_ctx=4096,
            verbose=False,
        )
    text_slice = text[:3000]
    prompt = f"""Извлеки из текста именованные сущности: персоны (PER), организации (ORG), локации (LOC).
Используй только типы PER, ORG, LOC. Ответ — только JSON-массив объектов с полями "text" и "type".
Пример: [{{"text": "АО ВДНХ", "type": "ORG"}}, {{"text": "Иванов И.И.", "type": "PER"}}]

Текст:
{text_slice}

Ответ — только массив JSON:
["""
    try:
        out = _ner_llama_model(
            prompt,
            max_tokens=NER_LLAMA_MAX_TOKENS,
            temperature=NER_LLAMA_TEMPERATURE,
            stop=["]\n", "\n\n"],
        )
        raw = (out.get("choices") or [{}])[0].get("text", "").strip()
    except Exception:
        return _ner_fallback(text)
    if DEBUG_NER:
        _log_ner_prompt(prompt, raw_response=raw, model_path=str(NER_LLAMA_MODEL_PATH))
    if not raw:
        return _ner_fallback(text)
    raw = "[" + raw
    if not raw.rstrip().endswith("]"):
        raw = raw.rstrip().rstrip(",") + "]"
    entities = _parse_ner_json(raw, text)
    if not entities:
        return _ner_fallback(text)
    return entities


def _parse_ner_json(raw: str, text: str) -> List[Dict]:
    """Парсит JSON-массив сущностей из ответа LLM, подставляет start/end по вхождению в text."""
    raw = raw.strip()
    start = raw.find("[")
    if start == -1:
        return []
    depth, end = 0, -1
    for i in range(start, len(raw)):
        if raw[i] == "[":
            depth += 1
        elif raw[i] == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end == -1:
        last_brace = raw.rfind("}")
        if last_brace > start:
            raw = raw[start:last_brace + 1] + "]"
        else:
            raw = raw[start:]
    else:
        raw = raw[start:end]
    try:
        arr = json.loads(raw)
    except json.JSONDecodeError:
        out = []
        for m in re.finditer(r'\{"text"\s*:\s*"([^"]*)"\s*,\s*"type"\s*:\s*"([^"]*)"\}', raw):
            t, typ = m.group(1).strip(), m.group(2).strip().upper()
            if t and typ in ("PER", "ORG", "LOC"):
                pos = text.find(t)
                out.append({"text": t, "type": typ, "start": pos if pos >= 0 else 0, "end": (pos + len(t)) if pos >= 0 else 0})
        return out
    result = []
    for item in arr:
        if not isinstance(item, dict):
            continue
        t = (item.get("text") or "").strip()
        typ = (item.get("type") or "ORG").strip().upper()
        if not t or typ not in ("PER", "ORG", "LOC"):
            continue
        pos = text.find(t)
        if pos < 0:
            pos = text.find(" ".join(t.split()))
        result.append({
            "text": t,
            "type": typ,
            "start": pos if pos >= 0 else 0,
            "end": (pos + len(t)) if pos >= 0 else 0,
        })
    return result


def _ner_natasha(text: str) -> List[Dict]:
    from natasha import Segmenter, MorphVocab, NewsEmbedding, NewsMorphTagger, NewsNERTagger, Doc
    segmenter = Segmenter()
    morph_vocab = MorphVocab()
    emb = NewsEmbedding()
    morph_tagger = NewsMorphTagger(emb)
    ner_tagger = NewsNERTagger(emb)
    doc = Doc(text)
    doc.segment(segmenter)
    doc.tag_morph(morph_tagger)
    doc.tag_ner(ner_tagger)
    out = []
    for span in doc.spans:
        if span.type not in ("PER", "ORG", "LOC"):
            continue
        t = span.text.strip()
        if len(t) < 2:
            continue
        out.append({"text": t, "type": span.type, "start": span.start, "end": span.stop})
    return out


def _ner_fallback(text: str) -> List[Dict]:
    """Fallback: фразы из заглавных слов (2+ подряд) и «АО/ООО/ИП …»."""
    out = []
    seen = set()
    # АО «ВДНХ», ООО "Рога", И.О. Фамилия
    for m in re.finditer(r"(?:(?:АО|ООО|ПАО|ИП|Департамент|Департамента)\s*[«\"]?[\w\s]+[»\"]?|(?:[А-ЯЁ][а-яё]+\s+)+[А-ЯЁ][а-яё]+)", text):
        t = m.group(0).strip()
        if len(t) < 3 or t.lower() in seen:
            continue
        seen.add(t.lower())
        if re.match(r"^(АО|ООО|ПАО|ИП|Департамент)", t):
            typ = "ORG"
        elif re.match(r"^[А-ЯЁ]\.\s*[А-ЯЁ]\.", t) or re.match(r"^[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+", t):
            typ = "PER"
        else:
            typ = "ORG"
        out.append({"text": t, "type": typ, "start": m.start(), "end": m.end()})
    return out


def _get_ner():
    global _ner_impl
    if _ner_impl is not None:
        return _ner_impl
    from ..config import (
        NER_LLAMA_MODEL_PATH,
        OPENROUTER_API_KEY,
        USE_OPENROUTER_FOR_NER,
    )

    if USE_OPENROUTER_FOR_NER and OPENROUTER_API_KEY:
        def _ner_openrouter_fallback(text: str) -> List[Dict]:
            try:
                return _ner_openrouter(text)
            except Exception:
                try:
                    return _ner_natasha(text)
                except Exception:
                    return _ner_fallback(text)
        _ner_impl = _ner_openrouter_fallback
    elif NER_LLAMA_MODEL_PATH and Path(NER_LLAMA_MODEL_PATH).exists():
        def _ner_with_fallback(text: str) -> List[Dict]:
            try:
                return _ner_llama(text)
            except Exception:
                try:
                    return _ner_natasha(text)
                except Exception:
                    return _ner_fallback(text)
        _ner_impl = _ner_with_fallback
    else:
        try:
            _ner_natasha("Тест Москва.")
            _ner_impl = _ner_natasha
        except Exception:
            _ner_impl = _ner_fallback
    return _ner_impl


def extract_entities(text: str) -> List[Dict]:
    return _get_ner()(text)
