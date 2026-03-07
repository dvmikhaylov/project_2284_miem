"""
Этап 3: извлечение связей между сущностями с помощью локального LLM (llama.cpp).

Поддерживается:
- llama-cpp-python (Llama) при заданном LLAMA_MODEL_PATH
- Иначе — fallback на паттерны (как в baseline)

Отладка: задайте переменную окружения DEBUG_LLM_RELATIONS=1 чтобы видеть
промпт, сырой ответ модели и результат парсинга.
"""
import os
import re
import json
from pathlib import Path
from typing import List, Dict, Optional

from ..config import (
    LLAMA_MODEL_PATH,
    LLAMA_TEMPERATURE,
    LLAMA_MAX_TOKENS,
    PROJECT_ROOT,
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
    USE_OPENROUTER_FOR_RELATIONS,
)

DEBUG_LLM = os.environ.get("DEBUG_LLM_RELATIONS", "").strip() in ("1", "true", "yes")


def _log_relations_prompt(prompt: str, raw_response: str, model_path: str):
    """Промпты связей — в output/prompts_relations.log."""
    msg = f"[RELATIONS] model={model_path}\n--- prompt ---\n{prompt[:2000]}\n--- end prompt ---\n--- response (first 800) ---\n{(raw_response or '')[:800]}\n--- end response ---\n\n"
    try:
        (PROJECT_ROOT / "output").mkdir(parents=True, exist_ok=True)
        with open(PROJECT_ROOT / "output" / "prompts_relations.log", "a", encoding="utf-8") as f:
            f.write(msg)
    except Exception:
        pass


def _find_entity(match_text: str, entity_texts: Dict) -> Optional[Dict]:
    """Находит сущность по частичному совпадению текста."""
    match_lower = match_text.lower()
    for ent_text, ent in entity_texts.items():
        if match_lower in ent_text.lower() or ent_text.lower() in match_lower:
            return ent
    return None


# Максимальное расстояние (символов) между сущностями для связи по proximity
PROXIMITY_MAX_DISTANCE = 150


def _entities_with_positions(text: str, entities: List[Dict]) -> List[Dict]:
    """Добавляет start/end по первому вхождению текста сущности в text."""
    result = []
    for e in entities:
        t = e.get("text", "")
        if not t:
            continue
        pos = text.find(t)
        if pos < 0:
            # пробуем без лишних пробелов
            t_compact = " ".join(t.split())
            pos = text.find(t_compact)
            if pos < 0:
                continue
            t = t_compact
        result.append({**e, "start": pos, "end": pos + len(t)})
    return result


def _extract_proximity_relations(text: str, entities: List[Dict]) -> List[Dict]:
    """Связи по близости сущностей в тексте (как в baseline)."""
    with_pos = _entities_with_positions(text, entities)
    if len(with_pos) < 2:
        return []
    sorted_entities = sorted(with_pos, key=lambda x: x["start"])
    relations = []
    seen = set()
    for i in range(len(sorted_entities) - 1):
        src, tgt = sorted_entities[i], sorted_entities[i + 1]
        if src["text"].lower() == tgt["text"].lower():
            continue
        dist = tgt["start"] - src["end"]
        if dist <= 0 or dist > PROXIMITY_MAX_DISTANCE:
            continue
        ctx_start = max(0, src["end"])
        ctx_end = min(len(text), tgt["start"] + 80)
        context = text[ctx_start:ctx_end].strip()
        if len(context) < 5:
            continue
        key = (src["text"].lower(), "связан_с", tgt["text"].lower())
        if key in seen:
            continue
        seen.add(key)
        relations.append({
            "source": src["text"],
            "target": tgt["text"],
            "relation": "связан_с",
            "source_type": src.get("type", "UNK"),
            "target_type": tgt.get("type", "UNK"),
            "context": context[:200],
        })
    return relations


def _relation_patterns(text: str, entities: List[Dict]) -> List[Dict]:
    """Fallback: извлечение связей по паттернам."""
    entity_texts = {e["text"]: e for e in entities}
    relations = []
    patterns = [
        (r"(\w+)\s+(?:заключил|подписал)\s+(?:договор|контракт)\s+(?:с|на)\s+(\w+)", "заключить_договор"),
        (r"(\w+)\s+(?:поставил|поставляет)\s+(\w+)", "поставить"),
        (r"(\w+)\s+(?:получил|получает)\s+(\w+)", "получить"),
        (r"(\w+)\s+(?:управляет|управление)\s+(\w+)", "управлять"),
        (r"(\w+)\s+(?:закупает|закупка)\s+(\w+)", "закупить"),
        (r"(\w+)\s+(?:контролирует)\s+(\w+)", "контролировать"),
    ]
    seen = set()
    for pattern, rel_type in patterns:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            s, t = m.group(1), m.group(2)
            src_ent = _find_entity(s, entity_texts)
            tgt_ent = _find_entity(t, entity_texts)
            if src_ent and tgt_ent and src_ent["text"] != tgt_ent["text"]:
                key = (src_ent["text"].lower(), rel_type, tgt_ent["text"].lower())
                if key not in seen:
                    seen.add(key)
                    relations.append({
                        "source": src_ent["text"],
                        "target": tgt_ent["text"],
                        "relation": rel_type,
                        "source_type": src_ent.get("type", "UNK"),
                        "target_type": tgt_ent.get("type", "UNK"),
                        "context": m.group(0),
                    })
    return relations


def _parse_llm_json_objects_greedy(s: str) -> List[Dict]:
    """Из обрезанной строки вида [{...}, {...} извлекает полные JSON-объекты по regex."""
    out = []
    # Ищем объекты с полями source, target, relation (значения в кавычках без экранирования)
    for m in re.finditer(
        r'\{\s*"source"\s*:\s*"([^"]*)"\s*,\s*"target"\s*:\s*"([^"]*)"\s*,\s*"relation"\s*:\s*"([^"]*)"\s*\}',
        s,
    ):
        src, tgt, rel = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        if src and tgt and src != tgt:
            out.append({"source": src, "target": tgt, "relation": rel or "связан_с"})
    return out


def _parse_llm_json(raw: str, entity_set: set) -> List[Dict]:
    """Достаёт из ответа LLM массив связей {source, target, relation}."""
    relations = []
    raw = raw.strip()
    # Убираем обёртку markdown ```json ... ```
    for prefix in ("```json", "```"):
        if raw.lower().startswith(prefix):
            raw = raw[len(prefix):].lstrip()
        if raw.endswith("```"):
            raw = raw[:-3].strip()
    # Ищем JSON-массив в ответе
    start = raw.find("[")
    if start == -1:
        # Одна связь в фигурных скобках
        for m in re.finditer(r"\{[^{}]*\"source\"[^{}]*\"target\"[^{}]*\}", raw):
            try:
                obj = json.loads(m.group(0))
                s, t = obj.get("source", "").strip(), obj.get("target", "").strip()
                if s and t and s != t:
                    relations.append({"source": s, "target": t, "relation": obj.get("relation", "связан_с")})
            except json.JSONDecodeError:
                continue
        return relations
    depth = 0
    end = -1
    for i in range(start, len(raw)):
        if raw[i] == "[":
            depth += 1
        elif raw[i] == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end == -1:
        # Ответ обрезан (нет "]") — берём до последней полной "}" и закрываем массив
        truncated = raw[start:]
        # Убираем лишнюю "[" в начале, если модель выдала "[["
        if truncated.startswith("[["):
            truncated = truncated[1:]
        last_brace = truncated.rfind("}")
        if last_brace >= 0:
            truncated = truncated[: last_brace + 1] + "]"
            try:
                arr = json.loads(truncated)
            except json.JSONDecodeError:
                arr = _parse_llm_json_objects_greedy(truncated)
        else:
            arr = _parse_llm_json_objects_greedy(truncated)
    else:
        try:
            arr = json.loads(raw[start:end])
        except json.JSONDecodeError:
            arr = _parse_llm_json_objects_greedy(raw[start:end])
    if not isinstance(arr, list):
        return relations
    for item in arr:
        if not isinstance(item, dict):
            continue
        s = (item.get("source") or item.get("source_entity") or "").strip()
        t = (item.get("target") or item.get("target_entity") or "").strip()
        if not s or not t or s == t:
            continue
        # Приводим к сущностям из списка (частичное совпадение)
        rel_type = (item.get("relation") or item.get("type") or "связан_с").strip()
        if isinstance(rel_type, str) and len(rel_type) > 50:
            rel_type = "связан_с"
        relations.append({"source": s, "target": t, "relation": rel_type})
    return relations


def _norm_for_match(s: str) -> str:
    """Нормализация для сопоставления: нижний регистр, убрать кавычки/скобки."""
    if not s:
        return ""
    s = s.lower().strip()
    for c in "«»\"'""''()":
        s = s.replace(c, "")
    return " ".join(s.split())


def _match_entity_to_list(name: str, entities: List[Dict]) -> Optional[Dict]:
    """Подбирает сущность из списка по точному или частичному совпадению (с нормализацией)."""
    name_norm = _norm_for_match(name)
    if not name_norm:
        return None
    for e in entities:
        t = e["text"]
        t_norm = _norm_for_match(t)
        if not t_norm:
            continue
        if name_norm == t_norm or name_norm in t_norm or t_norm in name_norm:
            return e
    return None


def _relations_via_llama(text: str, entities: List[Dict], model_path: Path) -> List[Dict]:
    """Извлечение связей через llama-cpp-python (модель в GGUF). Промпт на русском."""
    if DEBUG_LLM:
        print("[DEBUG_LLM] _relations_via_llama: model_path =", model_path)

    try:
        from llama_cpp import Llama
    except ImportError as e:
        if DEBUG_LLM:
            print("[DEBUG_LLM] llama_cpp не установлен:", e)
        return _relation_patterns(text, entities)

    entity_list = [e["text"] for e in entities][:25]
    text_slice = text[:2400]
    entities_str = ", ".join(f'"{x}"' for x in entity_list)

    # Короткий промпт и завершение на "[" — чтобы модель продолжила JSON, а не повторяла инструкцию
    prompt = f"""Найди в тексте связи между сущностями. Сущности (используй только их): {entities_str}

Текст:
{text_slice}

Формат ответа — только JSON-массив объектов с полями source, target, relation. Пример одной связи: {{"source": "А", "target": "Б", "relation": "связан_с"}}

Ответ — только массив JSON:
["""

    if DEBUG_LLM:
        print("[DEBUG_LLM] prompt (первые 800 символов):")
        print(prompt[:800])
        print("...[DEBUG_LLM] конец промпта")

    try:
        llm = Llama(model_path=str(model_path), n_ctx=2048, verbose=False)
        # Промпт уже заканчивается на "[" — модель дописывает содержимое массива
        out = llm(
            prompt,
            max_tokens=LLAMA_MAX_TOKENS,
            temperature=0.0,  # детерминированность для JSON
            stop=["]\n"],  # конец массива
        )
        raw = (out.get("choices") or [{}])[0].get("text", "")
        if raw.strip():
            raw = raw.strip()
            # Промпт заканчивается на "[", модель может выдать "[" или сразу "{"
            if not raw.startswith("["):
                raw = "[" + raw
            if not raw.rstrip().endswith("]"):
                raw = raw.rstrip().rstrip(",") + "]"
    except Exception as e:
        if DEBUG_LLM:
            print("[DEBUG_LLM] Ошибка вызова Llama:", e)
        return _relation_patterns(text, entities)

    if DEBUG_LLM:
        print("[DEBUG_LLM] сырой ответ модели (repr):")
        print(repr(raw[:1500]))
        print("[DEBUG_LLM] длина ответа:", len(raw))
    _log_relations_prompt(prompt, raw, str(model_path))

    parsed = _parse_llm_json(raw, {e["text"] for e in entities})
    # Дедупликация по (source, target, relation) — модель часто повторяет одну связь
    seen_raw = set()
    unique_parsed = []
    for item in parsed:
        key = (item["source"].lower(), item["target"].lower(), item.get("relation", "связан_с"))
        if key not in seen_raw:
            seen_raw.add(key)
            unique_parsed.append(item)
    if DEBUG_LLM:
        print("[DEBUG_LLM] после парсинга JSON: связей =", len(parsed), "→ уникальных =", len(unique_parsed))
        for i, p in enumerate(unique_parsed[:10]):
            print("  ", i, p)
        if len(unique_parsed) > 10:
            print("  ... и ещё", len(unique_parsed) - 10)

    result = []
    seen = set()
    for item in unique_parsed:
        src_ent = _match_entity_to_list(item["source"], entities)
        tgt_ent = _match_entity_to_list(item["target"], entities)
        if not src_ent or not tgt_ent or src_ent["text"] == tgt_ent["text"]:
            if DEBUG_LLM:
                reason = " (одна сущность)" if src_ent and tgt_ent and src_ent["text"] == tgt_ent["text"] else ""
                print("[DEBUG_LLM] отброшена связь:", item, "| src_ent=", src_ent is not None, "tgt_ent=", tgt_ent is not None, reason) 
            continue
        key = (src_ent["text"].lower(), item["relation"], tgt_ent["text"].lower())
        if key not in seen:
            seen.add(key)
            result.append({
                "source": src_ent["text"],
                "target": tgt_ent["text"],
                "relation": item["relation"][:80] if isinstance(item["relation"], str) else "связан_с",
                "source_type": src_ent.get("type", "UNK"),
                "target_type": tgt_ent.get("type", "UNK"),
                "context": "",
            })
    if DEBUG_LLM:
        print("[DEBUG_LLM] после сопоставления с сущностями: связей =", len(result))

    return result if result else _relation_patterns(text, entities)


def _relations_via_openrouter(text: str, entities: List[Dict]) -> List[Dict]:
    """Извлечение связей через OpenRouter (gpt-oss-120b:free)."""
    if not OPENROUTER_API_KEY:
        return _relation_patterns(text, entities)
    from ..openrouter_client import call_openrouter
    entity_list = [e["text"] for e in entities][:25]
    text_slice = text[:2400]
    entities_str = ", ".join(f'"{x}"' for x in entity_list)
    prompt = f"""Найди в тексте связи между сущностями. Сущности (используй только их): {entities_str}

Текст:
{text_slice}

Формат ответа — только JSON-массив объектов с полями source, target, relation. Пример: [{{"source": "А", "target": "Б", "relation": "связан_с"}}]
Ответ — только массив JSON, без markdown:"""
    raw = call_openrouter(
        prompt,
        api_key=OPENROUTER_API_KEY,
        model=OPENROUTER_MODEL,
        max_tokens=600,
        temperature=0.0,
    )
    if DEBUG_LLM:
        _log_relations_prompt(prompt, raw or "", "OpenRouter:" + OPENROUTER_MODEL)
    if not raw:
        return _relation_patterns(text, entities)
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
    parsed = _parse_llm_json(raw, {e["text"] for e in entities})
    seen_raw = set()
    unique_parsed = []
    for item in parsed:
        key = (item["source"].lower(), item["target"].lower(), item.get("relation", "связан_с"))
        if key not in seen_raw:
            seen_raw.add(key)
            unique_parsed.append(item)
    result = []
    seen = set()
    for item in unique_parsed:
        src_ent = _match_entity_to_list(item["source"], entities)
        tgt_ent = _match_entity_to_list(item["target"], entities)
        if not src_ent or not tgt_ent or src_ent["text"] == tgt_ent["text"]:
            continue
        key = (src_ent["text"].lower(), item["relation"], tgt_ent["text"].lower())
        if key not in seen:
            seen.add(key)
            result.append({
                "source": src_ent["text"],
                "target": tgt_ent["text"],
                "relation": item["relation"][:80] if isinstance(item["relation"], str) else "связан_с",
                "source_type": src_ent.get("type", "UNK"),
                "target_type": tgt_ent.get("type", "UNK"),
                "context": "",
            })
    return result if result else _relation_patterns(text, entities)


def _filter_proximity_by_llama(text: str, proximity_list: List[Dict], model_path: Path) -> List[Dict]:
    """Оставляет только те proximity-связи, которые LLM считает правдоподобными по тексту."""
    if not proximity_list:
        return []
    try:
        from llama_cpp import Llama
    except ImportError:
        return proximity_list
    text_slice = text[:2000]
    lines = [f"{i}: {r['source']} → {r['target']}" for i, r in enumerate(proximity_list)]
    prompt = f"""Текст:
{text_slice}

Связи по близости (могут быть лишние). Оставь только номера тех, которые реально имеют смысл в тексте. Остальные — бред, не включай.
{chr(10).join(lines)}

Ответ — только номера через запятую, например: 0, 2, 4
Ответ:"""
    try:
        llm = Llama(model_path=str(model_path), n_ctx=2048, verbose=False)
        out = llm(prompt, max_tokens=150, temperature=0.0, stop=["\n\n"])
        raw = (out.get("choices") or [{}])[0].get("text", "").strip()
    except Exception:
        return proximity_list
    keep_indices = set()
    for part in re.split(r"[\s,\[\]]+", raw):
        part = part.strip()
        if part.isdigit():
            i = int(part)
            if 0 <= i < len(proximity_list):
                keep_indices.add(i)
    if not keep_indices:
        return proximity_list
    result = [proximity_list[i] for i in sorted(keep_indices)]
    if DEBUG_LLM:
        print("[DEBUG_LLM] фильтр proximity: было", len(proximity_list), "оставлено", len(result))
    return result


def extract_relations(text: str, entities: List[Dict]) -> List[Dict]:
    """
    Связи: OpenRouter (gpt-oss-120b) или локальный LLM или паттерны; затем proximity.
    """
    use_openrouter = USE_OPENROUTER_FOR_RELATIONS and OPENROUTER_API_KEY
    model_path = LLAMA_MODEL_PATH
    path_obj = Path(model_path) if model_path else None
    use_local_llm = path_obj and path_obj.exists()
    if DEBUG_LLM:
        print("[DEBUG_LLM] extract_relations: OpenRouter =", use_openrouter, "local_llm =", use_local_llm)
    if use_openrouter:
        primary = _relations_via_openrouter(text, entities)
    elif use_local_llm:
        primary = _relations_via_llama(text, entities, path_obj)
    else:
        primary = _relation_patterns(text, entities)

    proximity = _extract_proximity_relations(text, entities)
    primary_keys = {(r["source"].lower(), r["relation"], r["target"].lower()) for r in primary}
    proximity_only = [r for r in proximity if (r["source"].lower(), r["relation"], r["target"].lower()) not in primary_keys]

    # Фильтр proximity только при локальном LLM (не при OpenRouter)
    if proximity_only and use_local_llm:
        proximity_only = _filter_proximity_by_llama(text, proximity_only, path_obj)
    for r in proximity_only:
        primary.append(r)
    return primary
