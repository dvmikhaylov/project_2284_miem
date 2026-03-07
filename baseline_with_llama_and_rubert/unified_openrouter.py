"""
Один вызов OpenRouter на документ: NER + связи + бизнес-процесс в одном ответе.
"""
import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from .config import (
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
    OPENROUTER_TIMEOUT,
    OPENROUTER_RETRIES,
    OPENROUTER_RETRY_DELAY,
    BUSINESS_PROCESSES_JSON,
    PROJECT_ROOT,
)
from .openrouter_client import call_openrouter

# Максимум символов документа в одном запросе (чтобы влезть в контекст)
MAX_DOC_CHARS = 8000


def _load_business_processes() -> List[Dict]:
    with open(BUSINESS_PROCESSES_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_unified_prompt(text: str) -> str:
    processes = _load_business_processes()
    processes_str = "\n".join(
        f"  - {p['category']} | {p['process']}" for p in processes
    )
    text_slice = text.strip()[:MAX_DOC_CHARS]
    if len(text.strip()) > MAX_DOC_CHARS:
        text_slice += "\n[... документ обрезан ...]"

    return f"""Ты — анализатор бизнес-документов.

Верни ТОЛЬКО JSON без пояснений, комментариев и markdown.

Задача:
Из текста документа извлечь:
1. ключевые сущности первого плана
2. акторов
3. основные цепочки бизнес-действий

Извлекай только сущности и связи, имеющие бизнес-смысл.
Игнорируй мусор OCR, служебные фразы, обращения и случайные фрагменты текста.

--------------------------------------------------
1. ДОПУСТИМЫЕ ТИПЫ СУЩНОСТЕЙ
--------------------------------------------------

Используй ТОЛЬКО следующие значения поля type:

PERSON — физическое лицо  
ORG — организация или компания  
DEPARTMENT — подразделение, отдел, департамент, управление, служба  
POSITION — должность  
SYSTEM — информационная система или программный продукт  
DOC_TYPE — тип документа  
LOCATION — место или адрес  
DATE — дата или момент времени  
TASK_ACTION — действие или операция бизнес-процесса  
ISSUE_PROBLEM — проблема, замечание, ошибка, нарушение

Другие значения type использовать запрещено.

--------------------------------------------------
2. АКТОРЫ
--------------------------------------------------

Для сущностей типов

PERSON  
ORG  
DEPARTMENT  
POSITION  
SYSTEM  

дополнительно указывай поля:

actor_category  
actor_subcategory  
role_in_process  
is_internal

Для остальных типов (DATE, DOC_TYPE, TASK_ACTION, ISSUE_PROBLEM, LOCATION)
эти поля НЕ добавляй.

--------------------------------------------------
3. КАТЕГОРИИ АКТОРОВ
--------------------------------------------------

Допустимые actor_category:

INTERNAL  
EXTERNAL  
INDIVIDUAL  
SYSTEM  
UNKNOWN

--------------------------------------------------
4. ПОДКАТЕГОРИИ АКТОРОВ
--------------------------------------------------

Для INTERNAL:

DEPARTMENT  
TEAM  
BRANCH  
SUBSIDIARY  
BUSINESS_UNIT  
LEGAL  
IT  
FINANCE  
HR  
PROCUREMENT  
OPERATIONS  
SECURITY  
UNKNOWN_INTERNAL_ORG  
UNKNOWN_INTERNAL_UNIT

Для EXTERNAL:

CONTRACTOR  
SUPPLIER  
PARTNER  
CLIENT  
GOVERNMENT_BODY  
REGULATOR  
AUDITOR  
CONSULTANT  
OUTSOURCER  
UNKNOWN_EXTERNAL_ORG

Для INDIVIDUAL:

EMPLOYEE  
MANAGER  
EXECUTIVE  
SPECIALIST  
SIGNATORY  
APPLICANT  
CONTACT_PERSON  
UNKNOWN_PERSON

Для SYSTEM:

EDMS  
ERP  
CRM  
BPM  
SERVICE_DESK  
EMAIL  
PORTAL  
ANALYTICS  
DATABASE  
FILE_STORAGE  
UNKNOWN_SYSTEM

Для UNKNOWN:

OTHER  
UNRESOLVED

--------------------------------------------------
5. РОЛИ В ПРОЦЕССЕ
--------------------------------------------------

Допустимые role_in_process:

INITIATOR  
EXECUTOR  
APPROVER  
REVIEWER  
CONTROLLER  
RECIPIENT  
SIGNER  
OBSERVER  
SOURCE_SYSTEM  
TARGET_SYSTEM  
UNKNOWN_ROLE

Если роль не указана явно в тексте — используй UNKNOWN_ROLE.

НЕ угадывай роль по контексту.

--------------------------------------------------
6. ОПРЕДЕЛЕНИЕ INTERNAL / EXTERNAL
--------------------------------------------------

Если из текста можно понять, что организация является частью компании,
используй:

actor_category = INTERNAL

Если организация является внешней компанией:

actor_category = EXTERNAL

Если это человек внутри организации:

actor_category = INTERNAL

Если невозможно определить:

actor_category = UNKNOWN

--------------------------------------------------
7. POSITION
--------------------------------------------------

POSITION — это должность, а не человек.

Для POSITION:

actor_category = INDIVIDUAL  
actor_subcategory определяется по смыслу (MANAGER, SPECIALIST и т.п.)

Если невозможно определить — UNKNOWN_PERSON.

--------------------------------------------------
8. SYSTEM
--------------------------------------------------

SYSTEM — это программные системы.

Примеры:

1С Документооборот → EDMS  
SAP → ERP  
Jira → SERVICE_DESK  
Bitrix → CRM  

Если тип системы неясен:

actor_subcategory = UNKNOWN_SYSTEM

--------------------------------------------------
9. TASK_ACTION
--------------------------------------------------

TASK_ACTION должен обозначать само действие процесса.

Извлекай краткую форму действия.

Правильно:

устранение замечаний  
согласование документа  
подписание документа  
создание задачи

Неправильно:

сроки устранения замечаний  
необходимость устранения замечаний  
информация о сроках устранения замечаний

Не объединяй действие и обстоятельства в одну сущность.

--------------------------------------------------
10. ISSUE_PROBLEM
--------------------------------------------------

ISSUE_PROBLEM обозначает проблему процесса.

Примеры:

замечания  
ошибка  
задержка  
несогласование  
нарушение срока  
доработка

--------------------------------------------------
11. ПРАВИЛА ЦЕПОЧЕК
--------------------------------------------------

Извлекай только ключевые цепочки бизнес-действий.

Формат:

[субъект] -> [действие] -> [объект]

Субъект может быть:

PERSON  
ORG  
DEPARTMENT  
POSITION  
SYSTEM

Объект может быть:

PERSON  
ORG  
DEPARTMENT  
POSITION  
SYSTEM  
DOC_TYPE  
TASK_ACTION  
ISSUE_PROBLEM  
LOCATION  
DATE

Используй краткую форму действия через underscore.

Примеры:

создать_задачу  
подписать_документ  
согласовать_лист  
направить_запрос  
устранить_замечания

Не создавай цепочки если:

действие абстрактное  
связь не имеет бизнес-смысла  
субъект не способен выполнить действие  
цепочка дублирует другую

--------------------------------------------------
12. СУЩНОСТИ ПЕРВОГО ПЛАНА
--------------------------------------------------

Извлекай только важные сущности:

участники документооборота  
подразделения  
системы  
документы  
задачи  
проблемы  
даты и сроки

НЕ извлекай:

обращения  
шапки документов  
служебные фразы  
мусор OCR

--------------------------------------------------
13. БИЗНЕС-ПРОЦЕСС
--------------------------------------------------

Определи, к какому бизнес-процессу относится документ. Выбери ОДИН процесс из списка ниже.
Поле "business_process": объект с полями "category" и "process" (точные значения из списка).

Список бизнес-процессов (выбери один):
{processes_str}

--------------------------------------------------
14. ФОРМАТ ВЫВОДА
--------------------------------------------------

Верни JSON строго такого вида:

{
  "entities": [
    {
      "id": 0,
      "text": "АО «ВДНХ»",
      "type": "ORG",
      "actor_category": "INTERNAL",
      "actor_subcategory": "UNKNOWN_INTERNAL_ORG",
      "role_in_process": "UNKNOWN_ROLE",
      "is_internal": true
    }
  ],
  "relation_chains": [
    ["Сыч Е.А.", "подписать_документ", "лист согласования"]
  ],
  "business_process": {
    "category": "Юридические и комплаенс",
    "process": "Договорная работа"
  }
}

--------------------------------------------------
15. ДОПОЛНИТЕЛЬНЫЕ ПРАВИЛА
--------------------------------------------------

Верни только валидный JSON.  
Не добавляй текст вне JSON.  
Не добавляй поля, которых нет в схеме.  
Если сущностей или цепочек нет — верни пустые массивы.  
Не придумывай факты, которых нет в тексте.

---

Документ:
---
{text_slice}
"""


def _parse_unified_response(raw: str) -> Tuple[List[Dict], List[Dict], List[list], Dict]:
    """Парсит ответ модели. Возвращает (entities, relations, relation_chains, business_process)."""
    raw = raw.strip()
    if raw.lower().startswith("```"):
        raw = re.sub(r"^```\w*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw)
    start = raw.find("{")
    if start >= 0:
        raw = raw[start:]
    depth = 0
    for i, c in enumerate(raw):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and i < len(raw) - 1:
                raw = raw[: i + 1]
                break
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = _parse_unified_fallback(raw)
    entities = data.get("entities") or []
    relations = data.get("relations") or []
    relation_chains = data.get("relation_chains") or []
    bp = data.get("business_process") or {}
    if not isinstance(entities, list):
        entities = []
    if not isinstance(relations, list):
        relations = []
    if not isinstance(relation_chains, list):
        relation_chains = []
    if not isinstance(bp, dict):
        bp = {}
    # Если есть relation_chains, но нет relations — строим relations из цепочек
    if not relations and relation_chains:
        for chain in relation_chains:
            if isinstance(chain, (list, tuple)) and len(chain) >= 3:
                relations.append({
                    "source": str(chain[0]).strip(),
                    "target": str(chain[2]).strip(),
                    "relation": str(chain[1]).strip() if len(chain) > 1 else "связан_с",
                })
    return entities, relations, relation_chains, bp


def _parse_unified_fallback(raw: str) -> dict:
    """Вытаскивает entities, relations, relation_chains, business_process по кускам."""
    out = {"entities": [], "relations": [], "relation_chains": [], "business_process": {}}
    for m in re.finditer(r'"entities"\s*:\s*\[(.*?)\]', raw, re.DOTALL):
        try:
            arr = json.loads("[" + m.group(1) + "]")
            if isinstance(arr, list):
                out["entities"] = [x for x in arr if isinstance(x, dict) and x.get("text")]
        except Exception:
            pass
    for m in re.finditer(r'"relations"\s*:\s*\[(.*?)\]', raw, re.DOTALL):
        try:
            arr = json.loads("[" + m.group(1) + "]")
            if isinstance(arr, list):
                out["relations"] = [x for x in arr if isinstance(x, dict) and x.get("source") and x.get("target")]
        except Exception:
            pass
    for m in re.finditer(r'"relation_chains"\s*:\s*\[(.*?)\]', raw, re.DOTALL):
        try:
            arr = json.loads("[" + m.group(1) + "]")
            if isinstance(arr, list):
                out["relation_chains"] = [x for x in arr if isinstance(x, (list, tuple)) and len(x) >= 3]
        except Exception:
            pass
    if not out["relations"] and out["relation_chains"]:
        for chain in out["relation_chains"]:
            out["relations"].append({
                "source": str(chain[0]).strip(),
                "target": str(chain[2]).strip(),
                "relation": str(chain[1]).strip() if len(chain) > 1 else "связан_с",
            })
    for m in re.finditer(r'"business_process"\s*:\s*\{([^}]+)\}', raw):
        try:
            obj = json.loads("{" + m.group(1) + "}")
            if isinstance(obj, dict):
                out["business_process"] = obj
        except Exception:
            pass
    return out


# Допустимые типы сущностей по спецификации заказчика (PDF)
ALLOWED_ENTITY_TYPES = frozenset({
    "PERSON", "ORG", "DEPARTMENT", "POSITION", "SYSTEM",
    "DOC_TYPE", "LOCATION", "DATE", "TASK_ACTION", "ISSUE_PROBLEM",
})
# Типы-акторы: для них сохраняем actor_* поля
ACTOR_TYPES = frozenset({"PERSON", "ORG", "DEPARTMENT", "POSITION", "SYSTEM"})
TYPE_ALIASES = {"PER": "PERSON", "LOC": "LOCATION"}


def _normalize_entities(entities: List[Dict], text: str) -> List[Dict]:
    """Сохраняет все типы из спецификации и поля акторов (actor_category, role_in_process и т.д.)."""
    result = []
    for e in entities:
        if not isinstance(e, dict):
            continue
        t = (e.get("text") or "").strip()
        typ = (e.get("type") or "ORG").strip().upper()
        typ = TYPE_ALIASES.get(typ, typ)
        if not t:
            continue
        if typ not in ALLOWED_ENTITY_TYPES:
            typ = "ORG"
        pos = text.find(t)
        if pos < 0:
            pos = text.find(" ".join(t.split()))
        out = {
            "text": t,
            "type": typ,
            "start": pos if pos >= 0 else 0,
            "end": (pos + len(t)) if pos >= 0 else 0,
        }
        if typ in ACTOR_TYPES:
            for key in ("actor_category", "actor_subcategory", "role_in_process", "is_internal"):
                if key in e and e[key] is not None:
                    out[key] = e[key]
        result.append(out)
    return result


def _match_business_process(bp: Dict) -> Optional[Dict]:
    """Сопоставляет ответ модели со списком процессов, возвращает полную запись."""
    processes = _load_business_processes()
    cat = (bp.get("category") or "").strip()
    proc = (bp.get("process") or bp.get("subprocess") or "").strip()
    if not cat and not proc:
        return None
    for i, p in enumerate(processes):
        if (p["category"] == cat and p["process"] == proc) or p["process"] == proc or p["category"] == cat:
            return {
                "category": p["category"],
                "subprocess": p["process"],
                "number": i,
                "confidence": 0.9,
                "alternatives": [],
            }
    if cat or proc:
        return {
            "category": cat or "Не указано",
            "subprocess": proc or "Не указано",
            "number": 0,
            "confidence": 0.5,
            "alternatives": [],
        }
    return None


def process_document_unified(text: str) -> Optional[Dict]:
    """
    Один вызов OpenRouter: из документа получаем entities, relations, business_process.
    Возвращает словарь в формате результата пайплайна или None при ошибке/отсутствии ключа.
    """
    if not OPENROUTER_API_KEY:
        return None
    prompt = _build_unified_prompt(text)
    raw = call_openrouter(
        prompt,
        api_key=OPENROUTER_API_KEY,
        model=OPENROUTER_MODEL,
        max_tokens=2000,
        temperature=0.0,
        timeout=OPENROUTER_TIMEOUT,
        max_retries=OPENROUTER_RETRIES,
        retry_delay=OPENROUTER_RETRY_DELAY,
    )
    if not raw or not raw.strip():
        return None
    log_prompt_and_response(prompt, raw)
    try:
        entities_raw, relations_raw, relation_chains_raw, bp_raw = _parse_unified_response(raw)
    except Exception:
        return None
    entities_list = _normalize_entities(entities_raw, text)
    seen_ent = set()
    unique_entities = []
    for e in entities_list:
        k = e["text"].lower().strip()
        if k and k not in seen_ent:
            seen_ent.add(k)
            unique_entities.append(e)
    entity_texts = {e["text"].lower(): e for e in unique_entities}

    relations_list = []
    seen_rel = set()
    for r in relations_raw:
        if not isinstance(r, dict):
            continue
        src = (r.get("source") or "").strip()
        tgt = (r.get("target") or "").strip()
        rel = (r.get("relation") or "связан_с")[:80]
        if not src or not tgt:
            continue
        src_match = entity_texts.get(src.lower()) or next((e for e in unique_entities if src.lower() in e["text"].lower()), None)
        tgt_match = entity_texts.get(tgt.lower()) or next((e for e in unique_entities if tgt.lower() in e["text"].lower()), None)
        if src_match and tgt_match and src_match["text"] != tgt_match["text"]:
            key = (src_match["text"].lower(), rel, tgt_match["text"].lower())
            if key not in seen_rel:
                seen_rel.add(key)
                relations_list.append({
                    "source": src_match["text"],
                    "target": tgt_match["text"],
                    "relation": rel,
                    "source_type": src_match.get("type", "UNK"),
                    "target_type": tgt_match.get("type", "UNK"),
                    "context": "",
                })

    # Цепочки: из ответа модели (relation_chains) или собираем из relations
    if relation_chains_raw and isinstance(relation_chains_raw, list):
        chains = []
        for c in relation_chains_raw:
            if isinstance(c, (list, tuple)) and len(c) >= 3:
                chains.append([str(c[0]).strip(), str(c[1]).strip(), str(c[2]).strip()])
    else:
        chains = []
        rel_by_source = {}
        for r in relations_list:
            rel_by_source.setdefault(r["source"], []).append(r)
        for e in unique_entities:
            for r in rel_by_source.get(e["text"], []):
                chains.append([e["text"], r["relation"], r["target"]])

    business_process = _match_business_process(bp_raw)
    if not business_process:
        business_process = {
            "category": "Не определено",
            "subprocess": "Не определено",
            "number": 0,
            "confidence": 0.0,
            "alternatives": [],
        }

    # Сущности в формате заказчика: id, text, type, + actor_* при наличии
    def entity_to_output(i: int, e: Dict) -> Dict:
        out = {"id": i, "text": e["text"], "type": e["type"]}
        for key in ("actor_category", "actor_subcategory", "role_in_process", "is_internal"):
            if key in e:
                out[key] = e[key]
        return out

    return {
        "entities": [entity_to_output(i, e) for i, e in enumerate(unique_entities)],
        "relations": relations_list,
        "relation_chains": chains,
        "business_process": business_process,
        "statistics": {
            "total_entities": len(unique_entities),
            "total_relations": len(relations_list),
            "total_chains": len(chains),
            "text_length": len(text),
        },
    }


def log_prompt_and_response(prompt: str, raw: str) -> None:
    """Пишет промпт и ответ в лог."""
    log_file = PROJECT_ROOT / "output" / "prompts_unified.log"
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write("--- unified prompt ---\n")
            f.write(prompt[:4000])
            if len(prompt) > 4000:
                f.write("\n... [обрезано] ...\n")
            f.write("\n--- response ---\n")
            f.write(raw[:3000] if raw else "(пусто)")
            f.write("\n--- end ---\n\n")
    except Exception:
        pass
