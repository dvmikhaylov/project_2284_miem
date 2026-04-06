from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    Document,
    DocumentChain,
    DocumentEntity,
    DocumentProcessMatch,
    DocumentRelation,
    ProcessCatalog,
)
from ..schemas import DocumentSummary, UploadResponse, document_to_summary, upload_payload
from ..services.catalog_sync import PLACEHOLDER_CATEGORY, PLACEHOLDER_PROCESS
from ..services.ingest import enqueue_document_upload, run_upload_job

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.get("", response_model=List[DocumentSummary])
def list_documents(db: Session = Depends(get_db), limit: int = Query(100, le=500)):
    rows = (
        db.execute(select(Document).order_by(Document.uploaded_at.desc()).limit(limit))
        .scalars()
        .all()
    )
    return [document_to_summary(item) for item in rows]


@router.post("/upload", response_model=UploadResponse)
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    force: bool = Query(False),
    db: Session = Depends(get_db),
):
    raw = file.file.read()
    filename = file.filename or "upload"
    doc, status = enqueue_document_upload(db, filename=filename, file_bytes=raw, force=force)
    if status in ("reused", "already_processing", "error"):
        return upload_payload(doc, status)
    background_tasks.add_task(run_upload_job, doc.id, raw, filename)
    return upload_payload(doc, "accepted")


@router.get("/by-id/{document_id}", response_model=DocumentSummary)
def document_summary_by_id(document_id: int, db: Session = Depends(get_db)):
    row = db.get(Document, document_id)
    if row is None:
        raise HTTPException(404, "Документ не найден")
    return document_to_summary(row)


@router.delete("/by-id/{document_id}")
def delete_document_by_id(document_id: int, db: Session = Depends(get_db)):
    row = db.get(Document, document_id)
    if row is None:
        raise HTTPException(404, "Документ не найден")
    doc_id = row.id
    db.delete(row)
    db.commit()
    return {"deleted": True, "id": doc_id}


@router.get("/by-hash/{content_sha256}")
def document_detail(content_sha256: str, db: Session = Depends(get_db)):
    row = (
        db.execute(select(Document).where(Document.content_sha256 == content_sha256))
        .scalars()
        .first()
    )
    if row is None:
        raise HTTPException(404, "Документ не найден")
    entities = (
        db.execute(
            select(DocumentEntity)
            .where(DocumentEntity.document_id == row.id)
            .order_by(DocumentEntity.sort_index)
        )
        .scalars()
        .all()
    )
    relations = (
        db.execute(select(DocumentRelation).where(DocumentRelation.document_id == row.id))
        .scalars()
        .all()
    )
    chains = (
        db.execute(
            select(DocumentChain)
            .where(DocumentChain.document_id == row.id)
            .order_by(DocumentChain.sort_index)
        )
        .scalars()
        .all()
    )
    matches = db.execute(
        select(DocumentProcessMatch, ProcessCatalog)
        .join(ProcessCatalog, ProcessCatalog.id == DocumentProcessMatch.process_catalog_id)
        .where(DocumentProcessMatch.document_id == row.id)
        .order_by(DocumentProcessMatch.sort_rank)
    ).all()
    bps = []
    for match, process in matches:
        is_ph = (
            process.category == PLACEHOLDER_CATEGORY and process.process_name == PLACEHOLDER_PROCESS
        )
        bps.append(
            {
                "category": process.category,
                "subprocess": process.process_name,
                "priority": process.priority,
                "relevance": match.relevance,
                "process_free_label": match.process_free_label,
                "process_meso": match.process_meso,
                "process_macro": match.process_macro,
                "matched_catalog": not is_ph,
            }
        )
    return {
        "document": {
            "id": row.id,
            "content_sha256": row.content_sha256,
            "filename": row.filename,
            "status": row.status,
            "error_message": row.error_message,
            "uploaded_at": row.uploaded_at.isoformat() if row.uploaded_at else None,
            "processed_at": row.processed_at.isoformat() if row.processed_at else None,
            "second_pass_applied": row.second_pass_applied,
        },
        "entities": [
            {
                "text": entity.text,
                "type": entity.type,
                "actor_category": entity.actor_category,
                "actor_subcategory": entity.actor_subcategory,
                "role_in_process": entity.role_in_process,
                "is_internal": entity.is_internal,
            }
            for entity in entities
        ],
        "relations": [
            {
                "source": relation.source,
                "target": relation.target,
                "relation": relation.relation,
                "source_type": relation.source_type,
                "target_type": relation.target_type,
            }
            for relation in relations
        ],
        "relation_chains": [[chain.subject, chain.action, chain.object_text] for chain in chains],
        "business_processes": bps,
    }
