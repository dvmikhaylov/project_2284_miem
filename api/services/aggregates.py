from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from datetime import datetime
from typing import Any, DefaultDict, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import DECAY_HALF_LIFE_DAYS
from ..time_utils import utc_now
from ..models import (
    Document,
    DocumentEntity,
    DocumentProcessMatch,
    DocumentRelation,
    ProcessCatalog,
)
from ..services.catalog_sync import PLACEHOLDER_CATEGORY, PLACEHOLDER_PROCESS


def time_weight(uploaded_at: datetime, now: Optional[datetime] = None) -> float:
    if uploaded_at is None:
        return 1.0
    now = now or utc_now()
    hl = float(DECAY_HALF_LIFE_DAYS)
    if hl <= 0:
        return 1.0
    age_days = (now - uploaded_at).total_seconds() / 86400.0
    return math.pow(0.5, max(0.0, age_days) / hl)


def _is_placeholder(pc: Optional[ProcessCatalog]) -> bool:
    if not pc:
        return False
    return pc.category == PLACEHOLDER_CATEGORY and pc.process_name == PLACEHOLDER_PROCESS


def _entity_map(db: Session, document_id: int) -> Dict[str, DocumentEntity]:
    ents = (
        db.execute(select(DocumentEntity).where(DocumentEntity.document_id == document_id))
        .scalars()
        .all()
    )
    out: Dict[str, DocumentEntity] = {}
    for e in ents:
        k = (e.text or "").strip().lower()
        if k:
            out[k] = e
    return out


def _actor_bucket(source: str, ent_map: Dict[str, DocumentEntity], actor_group: str) -> str:
    src = (source or "").strip() or "—"
    if actor_group == "original":
        return src
    sl = src.lower()
    ent = ent_map.get(sl)
    if ent is None:
        for k, e in ent_map.items():
            if sl in k or k in sl:
                ent = e
                break
    if actor_group == "meso":
        if ent and ent.actor_subcategory:
            return str(ent.actor_subcategory)
        return src
    if actor_group == "macro":
        if ent and ent.actor_category:
            return str(ent.actor_category)
        return src
    return src


def _process_bucket(
    m: DocumentProcessMatch,
    pc: Optional[ProcessCatalog],
    process_group: str,
) -> str:
    if pc is None:
        return "f:—"
    if process_group == "catalog":
        if _is_placeholder(pc):
            fl = (m.process_free_label or m.process_meso or "—").strip()
            h = hashlib.sha256(fl.encode("utf-8")).hexdigest()[:14]
            return f"x:{m.process_catalog_id}:{h}"
        return f"c:{m.process_catalog_id}"
    if process_group == "macro":
        v = (m.process_macro or "").strip()
        if not v:
            v = (pc.category or "—")[:120]
        return f"m:{v}"
    if process_group == "meso":
        v = (m.process_meso or "").strip()
        if not v:
            v = (pc.process_name or "—")[:120]
        return f"s:{v}"
    fl = (m.process_free_label or m.process_meso or (pc.process_name if pc else "") or "—").strip()[:240]
    h = hashlib.sha256(fl.encode("utf-8")).hexdigest()[:16]
    return f"f:{h}"


def _process_label(key: str, m: DocumentProcessMatch, pc: Optional[ProcessCatalog]) -> str:
    if key.startswith("c:"):
        if pc and not _is_placeholder(pc):
            c = (pc.category or "")[:26]
            n = (pc.process_name or "")[:30]
            return f"{c} — {n}" if c else n
        return key
    if key.startswith("x:"):
        return (m.process_free_label or m.process_meso or "—")[:56]
    if key.startswith("m:"):
        return (m.process_macro or "—")[:56]
    if key.startswith("s:"):
        return (m.process_meso or (pc.process_name if pc else "") or "—")[:56]
    return (m.process_free_label or "—")[:56]


def _parse_catalog_id_from_key(process_key: str) -> Optional[int]:
    if process_key.startswith("c:"):
        rest = process_key[2:]
        if rest.isdigit():
            return int(rest)
    return None


def process_bubbles(db: Session, *, process_group: str = "catalog") -> List[Dict[str, Any]]:
    now = utc_now()
    proc_by_id: Dict[int, ProcessCatalog] = {
        p.id: p for p in db.execute(select(ProcessCatalog)).scalars().all()
    }
    per_key: DefaultDict[str, float] = defaultdict(float)
    labels: Dict[str, str] = {}
    docs = db.execute(select(Document).where(Document.status == "ok")).scalars().all()
    for d in docs:
        w = time_weight(d.uploaded_at, now)
        matches = (
            db.execute(select(DocumentProcessMatch).where(DocumentProcessMatch.document_id == d.id))
            .scalars()
            .all()
        )
        for m in matches:
            pc = proc_by_id.get(m.process_catalog_id)
            pk = _process_bucket(m, pc, process_group)
            per_key[pk] += w * m.relevance * m.priority
            if pk not in labels:
                labels[pk] = _process_label(pk, m, pc)
    if not per_key:
        return []
    mx = max(per_key.values()) or 1.0
    out: List[Dict[str, Any]] = []
    for pk, val in sorted(per_key.items(), key=lambda x: -x[1]):
        pid = _parse_catalog_id_from_key(pk)
        out.append(
            {
                "process_key": pk,
                "process_id": pid if pid is not None else -1,
                "category": "",
                "process_name": labels.get(pk, pk),
                "weight": round(val, 6),
                "weight_norm": round(val / mx, 6),
            }
        )
    return out


def heatmap_actor_action(
    db: Session, *, process_id: int, top_n: int = 25
) -> Tuple[List[str], List[str], List[List[float]]]:
    now = utc_now()
    cells: DefaultDict[Tuple[str, str], float] = defaultdict(float)
    docs = db.execute(select(Document).where(Document.status == "ok")).scalars().all()
    for d in docs:
        match = db.execute(
            select(DocumentProcessMatch).where(
                DocumentProcessMatch.document_id == d.id,
                DocumentProcessMatch.process_catalog_id == process_id,
            )
        ).scalars().first()
        if match is None:
            continue
        signal = match.relevance * match.priority
        w = time_weight(d.uploaded_at, now)
        contrib = w * signal
        rels = (
            db.execute(select(DocumentRelation).where(DocumentRelation.document_id == d.id))
            .scalars()
            .all()
        )
        for r in rels:
            key = (r.source, r.relation)
            cells[key] += contrib

    if not cells:
        return [], [], []

    actors = sorted({k[0] for k in cells.keys()})[:top_n]
    actions = sorted({k[1] for k in cells.keys()})[:top_n]
    matrix = []
    for a in actors:
        row = [cells.get((a, act), 0.0) for act in actions]
        matrix.append(row)
    flat_max = max((v for row in matrix for v in row), default=1.0) or 1.0
    matrix = [[round(v / flat_max, 6) for v in row] for row in matrix]
    return actors, actions, matrix


def _actor_process_contributions(
    db: Session,
    *,
    category: Optional[str] = None,
    process_group: str = "catalog",
    actor_group: str = "original",
) -> Tuple[
    DefaultDict[Tuple[str, str], float],
    Dict[str, str],
    Dict[Tuple[str, str], int],
]:
    now = utc_now()
    proc_by_id: Dict[int, ProcessCatalog] = {
        p.id: p for p in db.execute(select(ProcessCatalog)).scalars().all()
    }
    cells: DefaultDict[Tuple[str, str], float] = defaultdict(float)
    doc_ids: DefaultDict[Tuple[str, str], set] = defaultdict(set)
    labels: Dict[str, str] = {}

    docs = db.execute(select(Document).where(Document.status == "ok")).scalars().all()
    for d in docs:
        w = time_weight(d.uploaded_at, now)
        rels = (
            db.execute(select(DocumentRelation).where(DocumentRelation.document_id == d.id))
            .scalars()
            .all()
        )
        if not rels:
            continue
        ent_map = _entity_map(db, d.id)
        matches = (
            db.execute(select(DocumentProcessMatch).where(DocumentProcessMatch.document_id == d.id))
            .scalars()
            .all()
        )
        for m in matches:
            pc = proc_by_id.get(m.process_catalog_id)
            if not pc:
                continue
            if category is not None and process_group == "catalog" and pc.category != category:
                continue
            pk = _process_bucket(m, pc, process_group)
            if pk not in labels:
                labels[pk] = _process_label(pk, m, pc)
            signal = m.relevance * m.priority
            contrib = w * signal
            for r in rels:
                ak = _actor_bucket(r.source, ent_map, actor_group)
                cells[(ak, pk)] += contrib
                doc_ids[(ak, pk)].add(d.id)

    doc_counts = {k: len(v) for k, v in doc_ids.items()}
    return cells, labels, doc_counts


def heatmap_actor_subprocess(
    db: Session,
    *,
    category: Optional[str] = None,
    top_n_actors: int = 22,
    top_n_processes: int = 18,
    process_group: str = "catalog",
    actor_group: str = "original",
) -> Tuple[List[str], List[str], List[List[float]], List[int], List[str]]:
    cells, pk_labels, _ = _actor_process_contributions(
        db,
        category=category,
        process_group=process_group,
        actor_group=actor_group,
    )
    if not cells:
        return [], [], [], [], []

    proc_mass: DefaultDict[str, float] = defaultdict(float)
    for (_, pk), v in cells.items():
        proc_mass[pk] += v
    sorted_pkeys = sorted(proc_mass.keys(), key=lambda x: -proc_mass[x])[:top_n_processes]

    sub_cells = {(a, p): c for (a, p), c in cells.items() if p in sorted_pkeys}
    actor_mass: DefaultDict[str, float] = defaultdict(float)
    for (a, p), v in sub_cells.items():
        actor_mass[a] += v
    sorted_actors = sorted(actor_mass.keys(), key=lambda x: -actor_mass[x])[:top_n_actors]

    col_labels = [pk_labels.get(pk, pk)[:56] for pk in sorted_pkeys]
    col_ids = [_parse_catalog_id_from_key(pk) or -1 for pk in sorted_pkeys]
    col_keys = list(sorted_pkeys)

    matrix: List[List[float]] = []
    for a in sorted_actors:
        row = [sub_cells.get((a, pk), 0.0) for pk in sorted_pkeys]
        matrix.append(row)
    flat_max = max((v for row in matrix for v in row), default=1.0) or 1.0
    matrix = [[round(v / flat_max, 6) for v in row] for row in matrix]
    return sorted_actors, col_labels, matrix, col_ids, col_keys


def top_actor_subprocess(
    db: Session,
    *,
    category: Optional[str] = None,
    limit: int = 40,
    process_group: str = "catalog",
    actor_group: str = "original",
) -> List[Dict[str, Any]]:
    cells, pk_labels, doc_counts = _actor_process_contributions(
        db,
        category=category,
        process_group=process_group,
        actor_group=actor_group,
    )
    if not cells:
        return []
    merged: DefaultDict[Tuple[str, str], float] = defaultdict(float)
    for (a, pk), v in cells.items():
        merged[(a, pk)] += v
    ranked = sorted(merged.items(), key=lambda x: -x[1])[:limit]
    mx = ranked[0][1] if ranked else 1.0
    mx = mx or 1.0
    out: List[Dict[str, Any]] = []
    for (a, pk), v in ranked:
        pid = _parse_catalog_id_from_key(pk)
        lab = pk_labels.get(pk, pk)
        out.append(
            {
                "actor": a,
                "actor_key": a,
                "process_key": pk,
                "category": "",
                "subprocess": lab,
                "process_id": pid if pid is not None else -1,
                "documents_count": doc_counts.get((a, pk), 0),
                "weight": round(v, 6),
                "weight_norm": round(v / mx, 6),
            }
        )
    return out


def documents_for_actor_process(
    db: Session,
    *,
    process_id: Optional[int] = None,
    process_key: Optional[str] = None,
    actor: str,
    actor_group: str = "original",
    process_group: str = "catalog",
    limit: int = 50,
) -> List[Dict[str, Any]]:
    pk_want = (process_key or "").strip() or None
    if not pk_want and process_id is not None:
        pk_want = f"c:{process_id}"
    if not pk_want:
        return []

    now = utc_now()
    actor_want = (actor or "").strip() or "—"
    proc_by_id: Dict[int, ProcessCatalog] = {
        p.id: p for p in db.execute(select(ProcessCatalog)).scalars().all()
    }
    scored: List[Tuple[float, Document]] = []
    docs = db.execute(select(Document).where(Document.status == "ok")).scalars().all()
    for d in docs:
        w = time_weight(d.uploaded_at, now)
        rels = (
            db.execute(select(DocumentRelation).where(DocumentRelation.document_id == d.id))
            .scalars()
            .all()
        )
        if not rels:
            continue
        ent_map = _entity_map(db, d.id)
        matches = (
            db.execute(select(DocumentProcessMatch).where(DocumentProcessMatch.document_id == d.id))
            .scalars()
            .all()
        )
        doc_contrib = 0.0
        for m in matches:
            pc = proc_by_id.get(m.process_catalog_id)
            pk = _process_bucket(m, pc, process_group)
            if pk != pk_want:
                continue
            signal = m.relevance * m.priority
            for r in rels:
                ak = _actor_bucket(r.source, ent_map, actor_group)
                if ak != actor_want:
                    continue
                doc_contrib += w * signal
        if doc_contrib > 0:
            scored.append((doc_contrib, d))
    scored.sort(key=lambda x: -x[0])
    return [
        {
            "document_id": d.id,
            "filename": d.filename,
            "content_sha256": d.content_sha256,
            "contribution": round(c, 6),
        }
        for c, d in scored[:limit]
    ]


def top_triples(
    db: Session, *, process_id: int, limit: int = 30
) -> List[Dict[str, Any]]:
    now = utc_now()
    triples: DefaultDict[Tuple[str, str, str], float] = defaultdict(float)
    proc = db.get(ProcessCatalog, process_id)
    proc_label = f"{proc.category} — {proc.process_name}" if proc else ""

    docs = db.execute(select(Document).where(Document.status == "ok")).scalars().all()
    for d in docs:
        match = db.execute(
            select(DocumentProcessMatch).where(
                DocumentProcessMatch.document_id == d.id,
                DocumentProcessMatch.process_catalog_id == process_id,
            )
        ).scalars().first()
        if match is None:
            continue
        signal = match.relevance * match.priority
        w = time_weight(d.uploaded_at, now)
        contrib = w * signal
        rels = (
            db.execute(select(DocumentRelation).where(DocumentRelation.document_id == d.id))
            .scalars()
            .all()
        )
        for r in rels:
            key = (r.source, r.relation, proc_label)
            triples[key] += contrib

    ranked = sorted(triples.items(), key=lambda x: -x[1])[:limit]
    mx = ranked[0][1] if ranked else 1.0
    mx = mx or 1.0
    return [
        {
            "actor": k[0],
            "action": k[1],
            "process_subprocess": k[2],
            "weight": round(v, 6),
            "weight_norm": round(v / mx, 6),
        }
        for k, v in ranked
    ]
