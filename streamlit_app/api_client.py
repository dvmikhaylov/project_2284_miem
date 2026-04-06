import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000").rstrip("/")


def _port_from_api_url() -> int:
    raw = API_URL.strip()
    if not raw.lower().startswith("http"):
        raw = "http://" + raw.lstrip("/")
    p = urlparse(raw)
    if p.port is not None:
        return int(p.port)
    return 443 if p.scheme == "https" else 8000


def api_unreachable_hint() -> str:
    """Текст для UI: как поднять API без ошибки «No module named api»."""
    port = _port_from_api_url()
    return (
        f"По адресу `{API_URL}` ответа нет. Поднимите API **из корня проекта** (там, где папка `api/`):\n\n"
        f"`source .venv/bin/activate && export PYTHONPATH=. && "
        f"python -m uvicorn api.main:app --reload --host 127.0.0.1 --port {port}`\n\n"
        "Порт в этой команде должен **совпадать** с URL выше (или задайте `API_URL` перед запуском Streamlit).\n\n"
        "Проще всего одной командой: `./scripts/start_api_and_streamlit.sh` (API + UI, порты согласованы).\n\n"
        "Не ставьте процесс на паузу **Ctrl+Z** — освободите порты **Ctrl+C** или `kill`.\n\n"
        "Глобальный `uvicorn` из **pipx** без venv → часто `No module named 'fastapi'`. "
        "Используйте `.venv` и `python -m uvicorn` или `./scripts/start_api.sh`."
    )
TIMEOUT = 600.0
# Ответ upload приходит сразу (фон — на сервере); длинный таймаут не нужен.
UPLOAD_TIMEOUT = 120.0


def _client() -> httpx.Client:
    return httpx.Client(base_url=API_URL, timeout=TIMEOUT)


def _upload_client() -> httpx.Client:
    return httpx.Client(base_url=API_URL, timeout=UPLOAD_TIMEOUT)


def health() -> bool:
    try:
        r = httpx.get(f"{API_URL}/health", timeout=5.0)
        return r.status_code == 200
    except Exception:
        return False


def list_processes() -> List[Dict[str, Any]]:
    with _client() as c:
        r = c.get("/api/v1/catalog/processes")
        r.raise_for_status()
        return r.json()


def list_documents() -> List[Dict[str, Any]]:
    with _client() as c:
        r = c.get("/api/v1/documents")
        r.raise_for_status()
        return r.json()


def document_by_id(document_id: int) -> Dict[str, Any]:
    with _client() as c:
        r = c.get(f"/api/v1/documents/by-id/{document_id}")
        r.raise_for_status()
        return r.json()


def delete_document(document_id: int) -> Dict[str, Any]:
    with _client() as c:
        r = c.delete(f"/api/v1/documents/by-id/{document_id}")
        r.raise_for_status()
        return r.json()


def upload_file(data: bytes, filename: str, force: bool = False) -> Dict[str, Any]:
    with _upload_client() as c:
        r = c.post(
            "/api/v1/documents/upload",
            files={"file": (filename, data)},
            params={"force": force},
        )
        r.raise_for_status()
        return r.json()


def document_by_hash(content_sha256: str) -> Dict[str, Any]:
    with _client() as c:
        r = c.get(f"/api/v1/documents/by-hash/{content_sha256}")
        r.raise_for_status()
        return r.json()


def process_bubbles(process_group: str = "catalog") -> Dict[str, Any]:
    with _client() as c:
        r = c.get("/api/v1/dashboard/process-bubbles", params={"process_group": process_group})
        r.raise_for_status()
        return r.json()


def heatmap(process_id: int, top_n: int = 20) -> Dict[str, Any]:
    with _client() as c:
        r = c.get(
            "/api/v1/dashboard/heatmap",
            params={"process_id": process_id, "top_n": top_n},
        )
        r.raise_for_status()
        return r.json()


def heatmap_actor_process(
    category: Optional[str] = None,
    top_n_actors: int = 22,
    top_n_processes: int = 18,
    process_group: str = "catalog",
    actor_group: str = "original",
) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "top_n_actors": top_n_actors,
        "top_n_processes": top_n_processes,
        "process_group": process_group,
        "actor_group": actor_group,
    }
    if category:
        params["category"] = category
    with _client() as c:
        r = c.get("/api/v1/dashboard/heatmap-actor-process", params=params)
        r.raise_for_status()
        return r.json()


def top_actor_process(
    category: Optional[str] = None,
    limit: int = 40,
    process_group: str = "catalog",
    actor_group: str = "original",
) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "limit": limit,
        "process_group": process_group,
        "actor_group": actor_group,
    }
    if category:
        params["category"] = category
    with _client() as c:
        r = c.get("/api/v1/dashboard/top-actor-process", params=params)
        r.raise_for_status()
        return r.json()


def actor_process_documents(
    actor: str,
    limit: int = 50,
    *,
    process_id: Optional[int] = None,
    process_key: Optional[str] = None,
    process_group: str = "catalog",
    actor_group: str = "original",
) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "actor": actor,
        "limit": limit,
        "process_group": process_group,
        "actor_group": actor_group,
    }
    if process_id is not None:
        params["process_id"] = process_id
    if process_key is not None:
        params["process_key"] = process_key
    with _client() as c:
        r = c.get("/api/v1/dashboard/actor-process-documents", params=params)
        r.raise_for_status()
        return r.json()


def triples(process_id: int, limit: int = 40) -> Dict[str, Any]:
    with _client() as c:
        r = c.get(
            "/api/v1/dashboard/triples",
            params={"process_id": process_id, "limit": limit},
        )
        r.raise_for_status()
        return r.json()
