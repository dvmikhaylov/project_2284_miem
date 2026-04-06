import hashlib
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from NLP.openrouter_pipeline.config import OPENROUTER_API_KEY
from NLP.openrouter_pipeline.document_reader import DocumentReader
from NLP.openrouter_pipeline.unified_openrouter import process_document_unified

from ..database import SessionLocal
from ..time_utils import utc_now
from ..services.catalog_sync import PLACEHOLDER_CATEGORY, PLACEHOLDER_PROCESS, ensure_placeholder_process
from ..models import (
    Document,
    DocumentChain,
    DocumentEntity,
    DocumentProcessMatch,
    DocumentRelation,
    ProcessCatalog,
)

log = logging.getLogger(__name__)


def _user_facing_nlp_error(message: str) -> str:
    low = (message or "").lower()
    if "maximum context length" in low or (
        "context length" in low and "token" in low and "reduce" in low
    ):
        return "Документ слишком большой для обработки моделью в одном запросе."
    return message


def _pick_suffix(filename: str) -> str:
    suf = Path(filename).suffix.lower()
    return suf if suf in (".docx", ".pdf", ".txt") else ".bin"


def _clear_document_children(db: Session, doc: Document) -> None:
    for rel in list(doc.relations or []):
        db.delete(rel)
    for ch in list(doc.chains or []):
        db.delete(ch)
    for e in list(doc.entities or []):
        db.delete(e)
    for m in list(doc.process_matches or []):
        db.delete(m)
    db.flush()


def _upsert_document_stats(doc: Document, text: str, payload: Dict[str, Any]) -> None:
    doc.status = "ok"
    doc.error_message = None
    doc.text_length = len(text)
    doc.entity_count = len(payload.get("entities") or [])
    doc.relation_count = len(payload.get("relations") or [])
    doc.chain_count = len(payload.get("relation_chains") or [])
    doc.second_pass_applied = bool(
        (payload.get("statistics") or {}).get("second_pass_applied", False)
    )
    doc.processed_at = utc_now()


def _insert_entities(db: Session, doc_id: int, entities: list[dict]) -> None:
    for i, e in enumerate(entities):
        db.add(
            DocumentEntity(
                document_id=doc_id,
                sort_index=i,
                text=e.get("text") or "",
                type=e.get("type") or "ORG",
                actor_category=e.get("actor_category"),
                actor_subcategory=e.get("actor_subcategory"),
                role_in_process=e.get("role_in_process"),
                is_internal=e.get("is_internal"),
            )
        )


def _insert_relations(db: Session, doc_id: int, relations: list[dict]) -> None:
    for r in relations:
        db.add(
            DocumentRelation(
                document_id=doc_id,
                source=r.get("source") or "",
                target=r.get("target") or "",
                relation=r.get("relation") or "",
                source_type=r.get("source_type") or "UNK",
                target_type=r.get("target_type") or "UNK",
            )
        )


def _insert_chains(db: Session, doc_id: int, chains: List[Any]) -> None:
    for i, c in enumerate(chains):
        if isinstance(c, (list, tuple)) and len(c) >= 3:
            db.add(
                DocumentChain(
                    document_id=doc_id,
                    sort_index=i,
                    subject=str(c[0]),
                    action=str(c[1]),
                    object_text=str(c[2]),
                )
            )


def _insert_process_matches(db: Session, doc_id: int, business_processes: List[dict]) -> None:
    ensure_placeholder_process(db)
    ph = db.execute(
        select(ProcessCatalog).where(
            ProcessCatalog.category == PLACEHOLDER_CATEGORY,
            ProcessCatalog.process_name == PLACEHOLDER_PROCESS,
        )
    ).scalars().first()
    ph_id = ph.id if ph else None
    rank = 0
    for bp in business_processes:
        cat = (bp.get("category") or "").strip()
        proc = (bp.get("subprocess") or bp.get("process") or "").strip()
        free = (bp.get("process_free_label") or "").strip() or None
        meso = (bp.get("process_meso") or "").strip() or None
        macro = (bp.get("process_macro") or "").strip() or None
        rel = float(bp.get("relevance") or 0)
        pri = float(bp.get("priority") or 0)
        row = db.execute(
            select(ProcessCatalog).where(
                ProcessCatalog.category == cat,
                ProcessCatalog.process_name == proc,
            )
        ).scalars().first()
        if not row and ph_id is not None:
            row = ph
        if not row:
            continue
        db.add(
            DocumentProcessMatch(
                document_id=doc_id,
                process_catalog_id=row.id,
                relevance=max(0.0, min(1.0, rel)),
                priority=max(0.0, min(1.0, pri)),
                sort_rank=rank,
                process_free_label=free,
                process_meso=meso,
                process_macro=macro,
            )
        )
        rank += 1


def apply_success_analysis(
    db: Session,
    doc: Document,
    text: str,
    payload: Dict[str, Any],
) -> Document:
    _clear_document_children(db, doc)
    _upsert_document_stats(doc, text, payload)
    db.flush()
    _insert_entities(db, doc.id, payload.get("entities") or [])
    _insert_relations(db, doc.id, payload.get("relations") or [])
    _insert_chains(db, doc.id, payload.get("relation_chains") or [])
    _insert_process_matches(db, doc.id, payload.get("business_processes") or [])

    db.commit()
    db.refresh(doc)
    return doc


def fail_document(
    db: Session,
    doc: Document,
    message: str,
    *,
    text_length: int = 0,
) -> None:
    _clear_document_children(db, doc)
    doc.status = "error"
    doc.error_message = (message or "")[:2000]
    doc.text_length = text_length
    doc.entity_count = 0
    doc.relation_count = 0
    doc.chain_count = 0
    doc.second_pass_applied = False
    doc.processed_at = utc_now()
    db.commit()


def enqueue_document_upload(
    db: Session,
    *,
    filename: str,
    file_bytes: bytes,
    force: bool = False,
) -> Tuple[Document, str]:
    h = hashlib.sha256(file_bytes).hexdigest()
    existing = db.execute(
        select(Document).where(Document.content_sha256 == h)
    ).scalars().first()

    if existing and existing.status == "ok" and not force:
        return existing, "reused"

    if existing and existing.status == "processing" and not force:
        return existing, "already_processing"

    if existing:
        db.delete(existing)
        db.commit()

    if not OPENROUTER_API_KEY:
        doc = Document(
            content_sha256=h,
            filename=filename,
            status="error",
            error_message="OPENROUTER_API_KEY не задан на сервере API",
            text_length=0,
            processed_at=utc_now(),
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc, "error"

    doc = Document(
        content_sha256=h,
        filename=filename,
        status="processing",
        error_message=None,
        text_length=0,
        entity_count=0,
        relation_count=0,
        chain_count=0,
        second_pass_applied=False,
        processed_at=None,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc, "accepted"


def run_upload_job(doc_id: int, file_bytes: bytes, filename: str) -> None:
    db = SessionLocal()
    try:
        doc = db.get(Document, doc_id)
        if doc is None or doc.status != "processing":
            return

        if not OPENROUTER_API_KEY:
            fail_document(db, doc, "OPENROUTER_API_KEY не задан на сервере API")
            return

        suffix = _pick_suffix(filename)
        tmp_path = None
        text = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            text = DocumentReader.read_document(Path(tmp_path))
        except Exception as e:
            log.exception("read_document failed doc_id=%s", doc_id)
            fail_document(db, doc, str(e))
            return
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        if not text or not str(text).strip():
            fail_document(db, doc, "Пустой текст документа")
            return

        try:
            payload = process_document_unified(text)
        except Exception as e:
            log.exception("process_document_unified failed doc_id=%s", doc_id)
            doc = db.get(Document, doc_id)
            if doc is not None and doc.status == "processing":
                fail_document(
                    db, doc, _user_facing_nlp_error(str(e)), text_length=len(text)
                )
            return

        if payload is None:
            doc = db.get(Document, doc_id)
            if doc is not None and doc.status == "processing":
                fail_document(db, doc, "Модель не вернула результат", text_length=len(text))
            return

        doc = db.get(Document, doc_id)
        if doc is None or doc.status != "processing":
            return

        apply_success_analysis(db, doc, text, payload)
    except Exception as e:
        log.exception("run_upload_job doc_id=%s", doc_id)
        db.rollback()
        doc = db.get(Document, doc_id)
        if doc:
            fail_document(db, doc, str(e))
    finally:
        db.close()


def process_upload(
    db: Session,
    *,
    filename: str,
    file_bytes: bytes,
    force: bool = False,
) -> Tuple[Document, str]:
    doc, st = enqueue_document_upload(db, filename=filename, file_bytes=file_bytes, force=force)
    if st in ("reused", "already_processing", "error"):
        return doc, st
    if st == "accepted":
        h = doc.content_sha256
        run_upload_job(doc.id, file_bytes, filename)
        db.expire_all()
        doc = db.execute(select(Document).where(Document.content_sha256 == h)).scalars().first()
        return doc, "created" if doc and doc.status == "ok" else "error"
    return doc, st
