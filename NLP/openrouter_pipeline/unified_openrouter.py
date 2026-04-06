"""
Один вызов OpenRouter на документ: NER + связи + бизнес-процесс в одном ответе.
"""
import json
import re
from typing import List, Dict, Optional, Tuple

from .config import (
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
    OPENROUTER_TIMEOUT,
    OPENROUTER_RETRIES,
    OPENROUTER_RETRY_DELAY,
    OPENROUTER_MAX_TOKENS_UNIFIED,
    OPENROUTER_MAX_TOKENS_SECOND_PASS,
    OPENROUTER_MAX_DOC_CHARS,
    OPENROUTER_MAX_CONTEXT_INPUT_TOKENS,
    OPENROUTER_INPUT_CHARS_PER_TOKEN,
    OPENROUTER_CONTEXT_MARGIN_CHARS,
    OPENROUTER_SECOND_PASS,
    OPENROUTER_SECOND_PASS_MAX_JSON,
    BUSINESS_PROCESSES_JSON,
    PROJECT_ROOT,
)
from .openrouter_client import call_openrouter


def _load_business_processes() -> List[Dict]:
    with open(BUSINESS_PROCESSES_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def _assemble_unified_prompt(processes_str: str, text_slice: str) -> str:
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

Три уровня для сущностей-акторов: **text** — как в документе (неограниченно); **actor_subcategory** — средний закрытый слой (только значения из разделов 4–5); **actor_category** — малый слой (INTERNAL, EXTERNAL, INDIVIDUAL, SYSTEM, UNKNOWN).

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
11. ПРАВИЛА ЦЕПОЧЕК (процессный вид, без ФИО)
--------------------------------------------------

Извлекай только ключевые цепочки бизнес-действий.

Формат:

[субъект] -> [действие] -> [объект]

В **relation_chains** субъект и объект — это **текст сущности** из массива entities, но:

- **Запрещено** ставить в субъект или объект сущности type=PERSON (никаких «Иванов И.О.» в цепочках).
- Для людей в цепочке используй **POSITION** (должность из документа) или **DEPARTMENT**, либо **ORG** / **SYSTEM** по смыслу.
- ФИО всё равно извлекай отдельной сущностью PERSON (см. п.12b) — для аудита и поиска конкретного лица.

Субъект цепочки (тип сущности в entities):

ORG, DEPARTMENT, POSITION, SYSTEM

Объект цепочки:

ORG, DEPARTMENT, POSITION, SYSTEM, DOC_TYPE, TASK_ACTION, ISSUE_PROBLEM, LOCATION, DATE

Используй краткую форму действия через underscore.

Примеры **правильных** цепочек (должность/орг, не ФИО):

["Коммерческий директор", "подписать_документ", "договор"]  
["АО «Заказчик»", "оплатить_услуги", "акт выполненных работ"]  
["Отдел IT", "согласовать_изменение", "техническое задание"]

Не создавай цепочки если:

действие абстрактное или «про процесс в целом» без конкретного действия  
связь не имеет бизнес-смысла или дублирует другую  
субъект по типу не может выполнить действие над объектом  
оба конца — одна и та же сущность

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
12a. АКТОРЫ: БЕЗ «ПУСТЫХ» ПОДКАТЕГОРИЙ
--------------------------------------------------

Для PERSON используй actor_category = INDIVIDUAL (не INTERNAL как для органа).  
Старайся указать осмысленную actor_subcategory (SPECIALIST, MANAGER, SIGNATORY, EMPLOYEE и т.д.) и role_in_process, если это следует из текста.  
UNKNOWN_PERSON, UNKNOWN_INTERNAL_ORG и прочие UNKNOWN_* используй только если иначе никак.

--------------------------------------------------
12b. ДВА УРОВНЯ АКТОРОВ (матрица «роль/подразделение — процесс»)
--------------------------------------------------

1) **Аудит (NER):** извлекай PERSON с полным ФИО, если оно есть в тексте — чтобы потом сопоставить с конкретным человеком.

2) **Процессный слой:** для цепочек и для primary_actors в business_processes опирайся на **POSITION**, **DEPARTMENT**, **ORG**, **SYSTEM**, а не на ФИО.

Если в тексте есть и ФИО, и должность — заведи **обе** сущности; в relation_chains участвует **должность** (POSITION), не PERSON.

Если должность в документе не названа, но роль ясна по контексту (заказчик/исполнитель/подписант), добавь POSITION с коротким функциональным названием, например:
«Подписант со стороны заказчика», «Представитель исполнителя (внешний)», «Внутренний сотрудник заказчика» — и заполни actor_subcategory (MANAGER, SPECIALIST, SIGNATORY, …) и is_internal по смыслу.

Не создавай отдельные сущности ORG с text «Заказчик» / «Подрядчик», если в тексте уже названы реальные организации — используй их как ORG, а абстрактную «сторону» выражай через POSITION.

--------------------------------------------------
13. ТРИ УРОВНЯ: БИЗНЕС-ПРОЦЕСС И АКТОРЫ
--------------------------------------------------

**Процесс (три уровня):**
1) **process_description** — свободная формулировка из документа (1–3 предложения), как процесс назван или описан в тексте; не ограничивай себя справочником.
2) **process_meso** — ровно одно значение из **среднего** списка MESO ниже (подтип процесса).
3) **process_macro** — ровно одно значение из **малого** списка MACRO ниже (крупная группа). Должно соответствовать выбранному MESO по смыслу.

**Актор в сущностях (три уровня):**
- **text** — как в документе (неограниченно).
- **actor_subcategory** — средний уровень: только из списков подкатегорий из разделов 4–5 промпта (DEPARTMENT, EXECUTIVE, ERP, …).
- **actor_category** — малый уровень: только INTERNAL, EXTERNAL, INDIVIDUAL, SYSTEM, UNKNOWN.

Если процесс **однозначно совпадает** со строкой справочника (та же category + process), можешь **дополнительно** указать **category** и **process** как в справочнике — сервер использует это для привязки. Иначе опускай category/process и задавай только process_description + process_meso + process_macro.

**MESO (process_meso):**  
CONTRACT_DRAFTING, CONTRACT_SIGNING, CONTRACT_AMENDMENT, PROCUREMENT_TENDER, PROCUREMENT_ORDER, INVOICING_PAYMENT, BUDGET_PLANNING, REPORTING_CONTROL, HR_RECRUITING, HR_PAYROLL, HR_TRAINING, IT_INCIDENT, IT_CHANGE, IT_PROJECT, LEGAL_REVIEW, LEGAL_DISPUTE, COMPLIANCE_AUDIT, ASSET_MAINTENANCE, LOGISTICS_DELIVERY, SALES_DEAL, CUSTOMER_SUPPORT, STRATEGY_PLANNING, OTHER_PROCESS

**MACRO (process_macro):**  
LEGAL_COMPLIANCE, FINANCE, HR, IT_DIGITAL, PROCUREMENT, OPERATIONS, SALES_SERVICE, STRATEGY, OTHER_MACRO

Справочник организации (для опциональной привязки category/process):
{processes_str}

Документ может относиться к нескольким процессам. Для каждого — отдельный объект в "business_processes".

--------------------------------------------------
14. ФОРМАТ ВЫВОДА
--------------------------------------------------

Верни JSON строго такого вида (relations опциональны):

{{
  "entities": [
    {{
      "id": 0,
      "text": "АО «Горизонт»",
      "type": "ORG",
      "actor_category": "INTERNAL",
      "actor_subcategory": "BUSINESS_UNIT",
      "role_in_process": "INITIATOR",
      "is_internal": true
    }}
  ],
  "relation_chains": [
    ["Коммерческий директор", "подписать_документ", "договор"],
    ["АО «Горизонт»", "направить_акт", "акт выполненных работ"]
  ],
  "business_processes": [
    {{
      "process_description": "Согласование и подписание договора на сопровождение ПО между сторонами.",
      "process_meso": "CONTRACT_SIGNING",
      "process_macro": "LEGAL_COMPLIANCE",
      "relevance": 0.9,
      "primary_actors": [
        {{
          "entity_text": "Коммерческий директор",
          "actor_category": "INDIVIDUAL",
          "actor_subcategory": "EXECUTIVE",
          "role_in_process": "SIGNER"
        }},
        {{
          "entity_text": "АО «Горизонт»",
          "actor_category": "INTERNAL",
          "actor_subcategory": "BUSINESS_UNIT",
          "role_in_process": "INITIATOR"
        }}
      ]
    }}
  ]
}}

--------------------------------------------------
15. ДОПОЛНИТЕЛЬНЫЕ ПРАВИЛА
--------------------------------------------------

Верни только валидный JSON.  
Не добавляй текст вне JSON.  
Если сущностей, цепочек или процессов нет — пустые массивы.  
Не придумывай факты, которых нет в тексте.  
Субъекты и объекты в relation_chains должны совпадать с text из entities; **не используй** в цепочках text сущностей type=PERSON.

---

Документ:
---
{text_slice}
"""


def _doc_slice(text: str, processes_str: str) -> str:
    s = text.strip()
    explicit = OPENROUTER_MAX_DOC_CHARS
    max_ctx = OPENROUTER_MAX_CONTEXT_INPUT_TOKENS

    if max_ctx and max_ctx > 0:
        baseline = len(_assemble_unified_prompt(processes_str, ""))
        budget = int(max_ctx * OPENROUTER_INPUT_CHARS_PER_TOKEN) - baseline - OPENROUTER_CONTEXT_MARGIN_CHARS
        if explicit > 0:
            budget = min(budget, explicit)
        budget = max(budget, 8000)
        if len(s) > budget:
            s = (
                s[:budget]
                + "\n[... документ слишком большой для полного анализа в одном запросе; "
                "ниже показан только начальный фрагмент — модель опирается на него. ...]"
            )
        return s

    if explicit > 0:
        out = s[:explicit]
        if len(s) > explicit:
            out += "\n[... документ слишком большой; показан только фрагмент. ...]"
        return out
    return s


def _build_unified_prompt(text: str) -> str:
    processes = _load_business_processes()
    processes_str = "\n".join(
        f"  - priority={p.get('priority', 1)} | {p['category']} | {p['process']}" for p in processes
    )
    text_slice = _doc_slice(text, processes_str)
    return _assemble_unified_prompt(processes_str, text_slice)


def _parse_json_from_model(raw: str) -> Optional[dict]:
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
            if depth == 0:
                raw = raw[: i + 1]
                break
    try:
        out = json.loads(raw)
        return out if isinstance(out, dict) else None
    except json.JSONDecodeError:
        return None


def _parse_unified_response(
    raw: str,
) -> Tuple[List[Dict], List[Dict], List[list], Dict, List[Dict]]:
    """Возвращает entities, relations, relation_chains, legacy business_process, business_processes."""
    data = _parse_json_from_model(raw)
    if not isinstance(data, dict):
        data = _parse_unified_fallback(raw)
    entities = data.get("entities") or []
    relations = data.get("relations") or []
    relation_chains = data.get("relation_chains") or []
    bp = data.get("business_process") or {}
    bps = data.get("business_processes")
    if not isinstance(entities, list):
        entities = []
    if not isinstance(relations, list):
        relations = []
    if not isinstance(relation_chains, list):
        relation_chains = []
    if not isinstance(bp, dict):
        bp = {}
    if not isinstance(bps, list):
        bps = []
    # Если есть relation_chains, но нет relations — строим relations из цепочек
    if not relations and relation_chains:
        for chain in relation_chains:
            if isinstance(chain, (list, tuple)) and len(chain) >= 3:
                relations.append({
                    "source": str(chain[0]).strip(),
                    "target": str(chain[2]).strip(),
                    "relation": str(chain[1]).strip() if len(chain) > 1 else "связан_с",
                })
    return entities, relations, relation_chains, bp, bps


def _parse_unified_fallback(raw: str) -> dict:
    """Вытаскивает entities, relations, relation_chains, business_process по кускам."""
    out = {"entities": [], "relations": [], "relation_chains": [], "business_process": {}, "business_processes": []}
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
    for m in re.finditer(r'"business_processes"\s*:\s*\[', raw):
        start = m.end() - 1
        depth = 0
        for j in range(start, len(raw)):
            if raw[j] == "[":
                depth += 1
            elif raw[j] == "]":
                depth -= 1
                if depth == 0:
                    try:
                        arr = json.loads(raw[start : j + 1])
                        if isinstance(arr, list):
                            out["business_processes"] = [x for x in arr if isinstance(x, dict)]
                    except Exception:
                        pass
                    break
        break
    return out


def _compact_entities_for_second_pass(unique_entities: List[Dict]) -> List[Dict]:
    out: List[Dict] = []
    for e in unique_entities:
        d: Dict = {"text": e["text"], "type": e["type"]}
        for k in ("actor_category", "actor_subcategory", "role_in_process", "is_internal"):
            if k in e and e[k] is not None:
                d[k] = e[k]
        out.append(d)
    return out


def _truncate_second_pass_input(s: str) -> str:
    m = OPENROUTER_SECOND_PASS_MAX_JSON
    if m and m > 0 and len(s) > m:
        return s[:m] + "\n...[обрезано OPENROUTER_SECOND_PASS_MAX_JSON]..."
    return s


def _build_second_pass_prompt(pass_json: str) -> str:
    return f"""Ты — второй проход: нормализация и фильтрация графа после первого извлечения из документа.

Верни ТОЛЬКО валидный JSON без markdown и текста вне JSON.

Вход (первый проход):
{pass_json}

Правила:
1. Сохрани все сущности type=PERSON с тем же text (ФИО) — для аудита; не удаляй их.
2. Можно добавлять только новые сущности типов POSITION или DEPARTMENT (краткая роль/подразделение для матрицы «актор — процесс»), если в цепочках больше нельзя опереться на уже имеющиеся POSITION/DEPARTMENT/ORG/SYSTEM.
2b. **Запрещено** добавлять обобщающие ORG вроде «Заказчик», «Подрядчик», «Исполнитель», «Покупатель», если во входе уже есть конкретные организации (АО, ООО, ПАО и т.п.). В связях и цепочках используй **только** их text из входа, а роль «сторона договора» выражай через POSITION или actor_subcategory, не через новую ORG-заглушку.
3. В relations (source, target) и в relation_chains (первый и третий элемент) **нельзя** использовать text сущностей type=PERSON. Замени на POSITION из входа или на добавленную ролевую POSITION.
3a. Если во входных entities есть POSITION (должности), по смыслу первого графа добавь 1–3 цепочки, где **субъект — POSITION**, а объект — DOC_TYPE / TASK_ACTION / ORG (подписание, согласование, направление документа). Не выдумывай должности: только те POSITION, что уже есть или что ты добавляешь как новую сущность по п.2.
4. Убери дубликаты цепочек и связей, убери семантически пустое: абстрактные действия, несоответствие типам, тавтологии, цепочки где субъект не может выполнить действие над объектом.
5. Каждый endpoint в relations и relation_chains должен **точно** совпадать с text какой-либо сущности в итоговом entities.
6. Не добавляй business_processes и не меняй каталог процессов — их в ответе не включай.

Формат ответа строго:
{{
  "entities": [ {{ "text": "...", "type": "...", ... }} ],
  "relations": [ {{ "source": "...", "target": "...", "relation": "..." }} ],
  "relation_chains": [ ["субъект", "действие", "объект"] ]
}}
"""


def _parse_second_pass_response(raw: str) -> Optional[Tuple[List[Dict], List[Dict], List]]:
    data = _parse_json_from_model(raw)
    if not isinstance(data, dict):
        return None
    entities = data.get("entities")
    relations = data.get("relations") or []
    relation_chains = data.get("relation_chains") or []
    if not isinstance(entities, list) or not entities:
        return None
    if not isinstance(relations, list):
        relations = []
    if not isinstance(relation_chains, list):
        relation_chains = []
    if not relations and relation_chains:
        for chain in relation_chains:
            if isinstance(chain, (list, tuple)) and len(chain) >= 3:
                relations.append({
                    "source": str(chain[0]).strip(),
                    "target": str(chain[2]).strip(),
                    "relation": str(chain[1]).strip() if len(chain) > 1 else "связан_с",
                })
    return entities, relations, relation_chains


def log_second_pass_prompt_and_response(prompt: str, raw: Optional[str]) -> None:
    log_file = PROJECT_ROOT / "output" / "prompts_unified.log"
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write("--- second pass prompt ---\n")
            f.write(prompt[:6000])
            if len(prompt) > 6000:
                f.write("\n... [обрезано] ...\n")
            f.write("\n--- second pass response ---\n")
            f.write((raw or "")[:5000] if raw else "(пусто)")
            f.write("\n--- end second pass ---\n\n")
    except Exception:
        pass


# Допустимые типы сущностей по спецификации заказчика (PDF)
ALLOWED_ENTITY_TYPES = frozenset({
    "PERSON", "ORG", "DEPARTMENT", "POSITION", "SYSTEM",
    "DOC_TYPE", "LOCATION", "DATE", "TASK_ACTION", "ISSUE_PROBLEM",
})
# Типы-акторы: для них сохраняем actor_* поля
ACTOR_TYPES = frozenset({"PERSON", "ORG", "DEPARTMENT", "POSITION", "SYSTEM"})
TYPE_ALIASES = {"PER": "PERSON", "LOC": "LOCATION"}


def _norm_sub(s: Optional[str]) -> str:
    return (s or "").strip().upper().replace(" ", "_")


def _is_weak_actor_entity(e: Dict) -> bool:
    if e.get("type") not in ACTOR_TYPES:
        return False
    if _norm_sub(e.get("actor_category")) == "UNKNOWN":
        return True
    sub = _norm_sub(e.get("actor_subcategory"))
    if sub.startswith("UNKNOWN_"):
        return True
    if sub in ("UNRESOLVED", "OTHER"):
        return True
    return False


def _is_weak_primary_actor(pa: Dict) -> bool:
    if not isinstance(pa, dict):
        return True
    if _norm_sub(pa.get("actor_category")) == "UNKNOWN":
        return True
    sub = _norm_sub(pa.get("actor_subcategory"))
    if sub.startswith("UNKNOWN_"):
        return True
    if sub in ("UNRESOLVED", "OTHER"):
        return True
    return False


def _entity_name_known(name: str, lower_to_canon: Dict[str, str]) -> Optional[str]:
    """Возвращает канонический text из kept, если имя резолвится; иначе None."""
    nl = name.strip().lower()
    if not nl:
        return None
    if nl in lower_to_canon:
        return lower_to_canon[nl]
    for tl, canon in lower_to_canon.items():
        if nl == tl or nl in tl or tl in nl:
            return canon
    return None


def _filter_entities_and_graph(
    unique_entities: List[Dict],
    relations_raw: List[Dict],
    relation_chains_raw: List,
) -> Tuple[List[Dict], List[Dict], List[List[str]]]:
    kept = [e for e in unique_entities if not _is_weak_actor_entity(e)]
    lower_to_canon = {e["text"].lower(): e["text"] for e in kept}
    by_text = {e["text"]: e for e in kept}

    relations_list: List[Dict] = []
    seen_rel: set = set()
    for r in relations_raw:
        if not isinstance(r, dict):
            continue
        src = (r.get("source") or "").strip()
        tgt = (r.get("target") or "").strip()
        rel = (r.get("relation") or "связан_с")[:80]
        if not src or not tgt:
            continue
        cs = _entity_name_known(src, lower_to_canon)
        ct = _entity_name_known(tgt, lower_to_canon)
        if not cs or not ct or cs == ct:
            continue
        sm = by_text.get(cs)
        tm = by_text.get(ct)
        if not sm or not tm:
            continue
        key = (cs.lower(), rel, ct.lower())
        if key not in seen_rel:
            seen_rel.add(key)
            relations_list.append({
                "source": cs,
                "target": ct,
                "relation": rel,
                "source_type": sm.get("type", "UNK"),
                "target_type": tm.get("type", "UNK"),
                "context": "",
            })

    chains: List[List[str]] = []
    seen_ch: set = set()
    if relation_chains_raw and isinstance(relation_chains_raw, list):
        for c in relation_chains_raw:
            if not isinstance(c, (list, tuple)) or len(c) < 3:
                continue
            a = str(c[0]).strip()
            rel = str(c[1]).strip()
            b = str(c[2]).strip()
            ca = _entity_name_known(a, lower_to_canon)
            cb = _entity_name_known(b, lower_to_canon)
            if not ca or not cb or ca == cb:
                continue
            tup = (ca.lower(), rel.lower(), cb.lower())
            if tup not in seen_ch:
                seen_ch.add(tup)
                chains.append([ca, rel, cb])

    if not chains and relations_list:
        rel_by_source: Dict[str, List[Dict]] = {}
        for r in relations_list:
            rel_by_source.setdefault(r["source"], []).append(r)
        for e in kept:
            for r in rel_by_source.get(e["text"], []):
                chains.append([e["text"], r["relation"], r["target"]])

    return kept, relations_list, chains


def _person_text_lowers(kept: List[Dict]) -> set:
    return {e["text"].strip().lower() for e in kept if e.get("type") == "PERSON" and e.get("text")}


def _matches_person_endpoint(name: str, person_lower: set) -> bool:
    nl = name.strip().lower()
    if not nl:
        return False
    if nl in person_lower:
        return True
    for pl in person_lower:
        if nl == pl or nl in pl or pl in nl:
            return True
    return False


def _remove_person_endpoints_from_graph(
    kept: List[Dict],
    relations_list: List[Dict],
    chains: List[List[str]],
) -> Tuple[List[Dict], List[Dict], List[List[str]]]:
    """Не показывать ФИО в цепочках/связях: только POSITION/DEPARTMENT/ORG/SYSTEM и пр."""
    pl = _person_text_lowers(kept)
    if not pl:
        return kept, relations_list, chains

    new_rel = []
    seen: set = set()
    for r in relations_list:
        s, t = r.get("source", ""), r.get("target", "")
        if _matches_person_endpoint(str(s), pl) or _matches_person_endpoint(str(t), pl):
            continue
        k = (str(s).lower(), r.get("relation", ""), str(t).lower())
        if k not in seen:
            seen.add(k)
            new_rel.append(r)

    new_ch = []
    seen_c: set = set()
    for c in chains:
        if len(c) < 3:
            continue
        a, rel, b = str(c[0]), str(c[1]), str(c[2])
        if _matches_person_endpoint(a, pl) or _matches_person_endpoint(b, pl):
            continue
        tup = (a.lower(), rel.lower(), b.lower())
        if tup not in seen_c:
            seen_c.add(tup)
            new_ch.append([a, rel, b])

    return kept, new_rel, new_ch


def _catalog_max_priority(processes: List[Dict]) -> int:
    vals = [int(p.get("priority", 1) or 1) for p in processes]
    return max(vals) if vals else 1


def _find_catalog_row(processes: List[Dict], category: str, process: str) -> Optional[Tuple[int, Dict]]:
    cat = (category or "").strip()
    proc = (process or "").strip()
    for i, p in enumerate(processes):
        if p["category"] == cat and p["process"] == proc:
            return i, p
    for i, p in enumerate(processes):
        if p["process"] == proc and proc:
            return i, p
    return None


_EXTRACTED_CAT = "(извлечено)"
_EXTRACTED_PROC = "— вне каталога —"


def _match_catalog_loose(
    processes: List[Dict], free: str, meso: str, macro: str
) -> Optional[Tuple[int, Dict]]:
    free = (free or "").strip()
    meso = (meso or "").strip()
    macro = (macro or "").strip()
    if free:
        for i, p in enumerate(processes):
            pn = (p.get("process") or "").strip()
            if pn and (pn == free or free in pn or pn in free):
                return i, p
    if meso:
        mu = meso.upper()
        for i, p in enumerate(processes):
            pn = (p.get("process") or "").strip()
            cat = (p.get("category") or "").strip()
            if mu in pn.upper() or mu in cat.upper():
                return i, p
    if macro:
        ma = macro.upper()
        for i, p in enumerate(processes):
            cat = (p.get("category") or "").strip()
            if ma in cat.upper().replace(" ", "_"):
                return i, p
    return None


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _resolve_business_processes_list(
    bps_raw: List[Dict],
    bp_legacy: Dict,
    kept_entity_texts_lower: set,
) -> List[Dict]:
    processes = _load_business_processes()
    max_p = _catalog_max_priority(processes)
    rows_in: List[Dict] = []
    if isinstance(bps_raw, list):
        rows_in.extend(x for x in bps_raw if isinstance(x, dict))
    if not rows_in and isinstance(bp_legacy, dict) and (bp_legacy.get("category") or bp_legacy.get("process")):
        rows_in.append(bp_legacy)

    resolved: List[Dict] = []
    for row in rows_in:
        free = (row.get("process_description") or row.get("process_free_label") or "").strip()
        meso = (row.get("process_meso") or "").strip()
        macro = (row.get("process_macro") or "").strip()
        cat_legacy = (row.get("category") or "").strip()
        proc_legacy = (row.get("process") or row.get("subprocess") or "").strip()

        found: Optional[Tuple[int, Dict]] = None
        if cat_legacy and proc_legacy:
            found = _find_catalog_row(processes, cat_legacy, proc_legacy)
        if not found:
            found = _match_catalog_loose(processes, free, meso, macro)

        rel = row.get("relevance", row.get("confidence", 0.5))
        try:
            rel_f = _clamp01(float(rel))
        except (TypeError, ValueError):
            rel_f = 0.5

        primary = row.get("primary_actors") or []
        if not isinstance(primary, list):
            primary = []
        actors_out: List[Dict] = []
        for pa in primary:
            if not isinstance(pa, dict) or _is_weak_primary_actor(pa):
                continue
            et = (pa.get("entity_text") or pa.get("text") or "").strip()
            if not et:
                continue
            el = et.lower()
            if el not in kept_entity_texts_lower and not any(
                el in k or k in el for k in kept_entity_texts_lower
            ):
                continue
            entry = {
                "entity_text": et,
                "actor_category": pa.get("actor_category"),
                "actor_subcategory": pa.get("actor_subcategory"),
                "role_in_process": pa.get("role_in_process"),
            }
            actors_out.append({k: v for k, v in entry.items() if v is not None})

        if found:
            idx, p = found
            pri = int(p.get("priority", 1) or 1)
            priority_norm = round((pri / max_p) if max_p else 1.0, 6)
            resolved.append(
                {
                    "category": p["category"],
                    "subprocess": p["process"],
                    "number": idx,
                    "priority": priority_norm,
                    "relevance": round(rel_f, 6),
                    "primary_actors": actors_out,
                    "alternatives": [],
                    "process_free_label": free or p["process"],
                    "process_meso": meso or "",
                    "process_macro": macro or "",
                }
            )
        elif free or meso or macro:
            resolved.append(
                {
                    "category": _EXTRACTED_CAT,
                    "subprocess": _EXTRACTED_PROC,
                    "number": -1,
                    "priority": 1.0,
                    "relevance": round(rel_f, 6),
                    "primary_actors": actors_out,
                    "alternatives": [],
                    "process_free_label": free or meso or macro,
                    "process_meso": meso or "",
                    "process_macro": macro or "OTHER_MACRO",
                }
            )

    resolved.sort(
        key=lambda x: (
            -(x["relevance"] * x["priority"]),
            x["number"] if x["number"] >= 0 else 10**9,
        ),
    )
    return resolved


def _business_process_top(resolved: List[Dict]) -> Dict:
    if not resolved:
        return {
            "category": "Не определено",
            "subprocess": "Не определено",
            "number": 0,
            "priority": 0.0,
            "relevance": 0.0,
            "primary_actors": [],
            "alternatives": [],
        }
    top = resolved[0]
    alts = [
        {
            "category": r["category"],
            "subprocess": r["subprocess"],
            "number": r["number"],
            "priority": r["priority"],
            "relevance": r["relevance"],
        }
        for r in resolved[1:15]
    ]
    return {
        "category": top["category"],
        "subprocess": top["subprocess"],
        "number": top["number"],
        "priority": top["priority"],
        "relevance": top["relevance"],
        "primary_actors": top.get("primary_actors", []),
        "alternatives": alts,
    }


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


def process_document_unified(text: str) -> Optional[Dict]:
    """
    Проход 1: OpenRouter — NER + граф + business_processes из промпта.
    Проход 2 (если OPENROUTER_SECOND_PASS): нормализация entities/relations/relation_chains
    (цепочки без ФИО, фильтрация мусора); справочник процессов не меняется.
    """
    if not OPENROUTER_API_KEY:
        return None
    prompt = _build_unified_prompt(text)
    if OPENROUTER_MAX_CONTEXT_INPUT_TOKENS and OPENROUTER_MAX_CONTEXT_INPUT_TOKENS > 0:
        est_in_tok = max(1, int(len(prompt) / OPENROUTER_INPUT_CHARS_PER_TOKEN))
        completion_budget = OPENROUTER_MAX_CONTEXT_INPUT_TOKENS - est_in_tok - 4096
        max_tok = min(
            OPENROUTER_MAX_TOKENS_UNIFIED,
            max(1024, completion_budget),
        )
    else:
        max_tok = OPENROUTER_MAX_TOKENS_UNIFIED
    raw = call_openrouter(
        prompt,
        api_key=OPENROUTER_API_KEY,
        model=OPENROUTER_MODEL,
        max_tokens=max_tok,
        temperature=0.0,
        timeout=OPENROUTER_TIMEOUT,
        max_retries=OPENROUTER_RETRIES,
        retry_delay=OPENROUTER_RETRY_DELAY,
    )
    if not raw or not raw.strip():
        return None
    log_prompt_and_response(prompt, raw)
    try:
        entities_raw, relations_raw, relation_chains_raw, bp_raw, bps_raw = _parse_unified_response(raw)
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

    second_pass_applied = False
    if OPENROUTER_SECOND_PASS and unique_entities:
        pack = {
            "entities": _compact_entities_for_second_pass(unique_entities),
            "relations": relations_raw,
            "relation_chains": relation_chains_raw,
        }
        pass_json = _truncate_second_pass_input(json.dumps(pack, ensure_ascii=False))
        sp_prompt = _build_second_pass_prompt(pass_json)
        raw2 = None
        try:
            raw2 = call_openrouter(
                sp_prompt,
                api_key=OPENROUTER_API_KEY,
                model=OPENROUTER_MODEL,
                max_tokens=OPENROUTER_MAX_TOKENS_SECOND_PASS,
                temperature=0.0,
                timeout=OPENROUTER_TIMEOUT,
                max_retries=OPENROUTER_RETRIES,
                retry_delay=OPENROUTER_RETRY_DELAY,
            )
        except Exception:
            raw2 = None
        log_second_pass_prompt_and_response(sp_prompt, raw2)
        if raw2 and raw2.strip():
            parsed2 = _parse_second_pass_response(raw2)
            if parsed2:
                entities_sp, relations_raw, relation_chains_raw = parsed2
                entities_list_sp = _normalize_entities(entities_sp, text)
                seen2: set = set()
                unique_entities = []
                for e in entities_list_sp:
                    k = e["text"].lower().strip()
                    if k and k not in seen2:
                        seen2.add(k)
                        unique_entities.append(e)
                second_pass_applied = True

    kept, relations_list, chains = _filter_entities_and_graph(
        unique_entities, relations_raw, relation_chains_raw
    )
    kept, relations_list, chains = _remove_person_endpoints_from_graph(
        kept, relations_list, chains
    )
    kept_entity_texts_lower = {e["text"].lower() for e in kept}

    business_processes = _resolve_business_processes_list(
        bps_raw, bp_raw, kept_entity_texts_lower
    )
    business_process = _business_process_top(business_processes)

    # Сущности в формате заказчика: id, text, type, + actor_* при наличии
    def entity_to_output(i: int, e: Dict) -> Dict:
        out = {"id": i, "text": e["text"], "type": e["type"]}
        for key in ("actor_category", "actor_subcategory", "role_in_process", "is_internal"):
            if key in e:
                out[key] = e[key]
        return out

    return {
        "entities": [entity_to_output(i, e) for i, e in enumerate(kept)],
        "relations": relations_list,
        "relation_chains": chains,
        "business_process": business_process,
        "business_processes": business_processes,
        "statistics": {
            "total_entities": len(kept),
            "total_relations": len(relations_list),
            "total_chains": len(chains),
            "text_length": len(text),
            "second_pass_applied": second_pass_applied,
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
