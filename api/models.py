from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .time_utils import utc_now


class ProcessCatalog(Base):
    __tablename__ = "process_catalog"
    __table_args__ = (UniqueConstraint("category", "process_name", name="uq_cat_proc"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(512), nullable=False)
    process_name: Mapped[str] = mapped_column(String(512), nullable=False)
    priority_raw: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    priority: Mapped[float] = mapped_column(Float, nullable=False)
    catalog_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content_sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(1024), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    text_length: Mapped[int] = mapped_column(Integer, default=0)
    entity_count: Mapped[int] = mapped_column(Integer, default=0)
    relation_count: Mapped[int] = mapped_column(Integer, default=0)
    chain_count: Mapped[int] = mapped_column(Integer, default=0)
    second_pass_applied: Mapped[bool] = mapped_column(Boolean, default=False)

    entities = relationship("DocumentEntity", back_populates="document", cascade="all, delete-orphan")
    relations = relationship("DocumentRelation", back_populates="document", cascade="all, delete-orphan")
    chains = relationship("DocumentChain", back_populates="document", cascade="all, delete-orphan")
    process_matches = relationship(
        "DocumentProcessMatch", back_populates="document", cascade="all, delete-orphan"
    )


class DocumentEntity(Base):
    __tablename__ = "document_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    sort_index: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    actor_subcategory: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    role_in_process: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_internal: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    document = relationship("Document", back_populates="entities")


class DocumentRelation(Base):
    __tablename__ = "document_relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[str] = mapped_column(Text, nullable=False)
    relation: Mapped[str] = mapped_column(String(256), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), default="UNK")
    target_type: Mapped[str] = mapped_column(String(64), default="UNK")

    document = relationship("Document", back_populates="relations")


class DocumentChain(Base):
    __tablename__ = "document_chains"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    sort_index: Mapped[int] = mapped_column(Integer, default=0)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(String(256), nullable=False)
    object_text: Mapped[str] = mapped_column(Text, nullable=False)

    document = relationship("Document", back_populates="chains")


class DocumentProcessMatch(Base):
    __tablename__ = "document_process_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    process_catalog_id: Mapped[int] = mapped_column(ForeignKey("process_catalog.id"), index=True)
    relevance: Mapped[float] = mapped_column(Float, nullable=False)
    priority: Mapped[float] = mapped_column(Float, nullable=False)
    sort_rank: Mapped[int] = mapped_column(Integer, default=0)
    process_free_label: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    process_meso: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    process_macro: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    document = relationship("Document", back_populates="process_matches")
    process = relationship("ProcessCatalog")
