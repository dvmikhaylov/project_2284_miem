from typing import List, Optional

from pydantic import BaseModel

from .models import Document


class DocumentSummary(BaseModel):
    id: int
    content_sha256: str
    filename: str
    status: str
    uploaded_at: Optional[str] = None
    processed_at: Optional[str] = None
    entity_count: int = 0
    relation_count: int = 0
    chain_count: int = 0
    error_message: Optional[str] = None


class UploadDocumentInfo(BaseModel):
    id: int
    content_sha256: str
    filename: str
    processing_status: str
    error_message: Optional[str] = None
    entity_count: int = 0
    relation_count: int = 0
    chain_count: int = 0


class UploadResponse(BaseModel):
    status: str
    document: UploadDocumentInfo


class CatalogProcessItem(BaseModel):
    id: int
    category: str
    process_name: str
    priority: float
    priority_raw: int


class DashboardHeatmapResponse(BaseModel):
    actors: List[str]
    actions: List[str]
    matrix: List[List[float]]


class DashboardActorProcessHeatmapResponse(BaseModel):
    actors: List[str]
    subprocess_labels: List[str]
    column_process_ids: List[int]
    column_keys: List[str]
    matrix: List[List[float]]


def document_to_summary(d: Document) -> DocumentSummary:
    return DocumentSummary(
        id=d.id,
        content_sha256=d.content_sha256,
        filename=d.filename,
        status=d.status,
        uploaded_at=d.uploaded_at.isoformat() if d.uploaded_at else None,
        processed_at=d.processed_at.isoformat() if d.processed_at else None,
        entity_count=d.entity_count,
        relation_count=d.relation_count,
        chain_count=d.chain_count,
        error_message=d.error_message,
    )


def upload_payload(doc: Document, upload_status: str) -> UploadResponse:
    return UploadResponse(
        status=upload_status,
        document=UploadDocumentInfo(
            id=doc.id,
            content_sha256=doc.content_sha256,
            filename=doc.filename,
            processing_status=doc.status,
            error_message=doc.error_message,
            entity_count=doc.entity_count,
            relation_count=doc.relation_count,
            chain_count=doc.chain_count,
        ),
    )
