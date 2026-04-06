from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import DashboardActorProcessHeatmapResponse, DashboardHeatmapResponse
from ..services import aggregates

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/process-bubbles")
def dashboard_bubbles(
    db: Session = Depends(get_db),
    process_group: str = Query(
        "catalog",
        description="catalog | macro | meso | free",
    ),
):
    if process_group not in ("catalog", "macro", "meso", "free"):
        raise HTTPException(422, "process_group must be catalog, macro, meso or free")
    return {"items": aggregates.process_bubbles(db, process_group=process_group)}


@router.get("/heatmap", response_model=DashboardHeatmapResponse)
def dashboard_heatmap(
    process_id: int = Query(..., description="ID из /api/v1/catalog/processes"),
    top_n: int = Query(20, le=80),
    db: Session = Depends(get_db),
):
    actors, actions, matrix = aggregates.heatmap_actor_action(db, process_id=process_id, top_n=top_n)
    return {"actors": actors, "actions": actions, "matrix": matrix}


@router.get("/heatmap-actor-process", response_model=DashboardActorProcessHeatmapResponse)
def dashboard_heatmap_actor_process(
    category: Optional[str] = Query(None, description="Только subprocess этой категории; без параметра — все категории"),
    top_n_actors: int = Query(22, ge=1, le=60),
    top_n_processes: int = Query(18, ge=1, le=60),
    process_group: str = Query("catalog", description="catalog | macro | meso | free"),
    actor_group: str = Query("original", description="original | meso | macro"),
    db: Session = Depends(get_db),
):
    if process_group not in ("catalog", "macro", "meso", "free"):
        raise HTTPException(422, "process_group must be catalog, macro, meso or free")
    if actor_group not in ("original", "meso", "macro"):
        raise HTTPException(422, "actor_group must be original, meso or macro")
    actors, labels, matrix, col_ids, col_keys = aggregates.heatmap_actor_subprocess(
        db,
        category=category,
        top_n_actors=top_n_actors,
        top_n_processes=top_n_processes,
        process_group=process_group,
        actor_group=actor_group,
    )
    return {
        "actors": actors,
        "subprocess_labels": labels,
        "column_process_ids": col_ids,
        "column_keys": col_keys,
        "matrix": matrix,
    }


@router.get("/top-actor-process")
def dashboard_top_actor_process(
    category: Optional[str] = Query(None),
    limit: int = Query(40, ge=1, le=200),
    process_group: str = Query("catalog"),
    actor_group: str = Query("original"),
    db: Session = Depends(get_db),
):
    if process_group not in ("catalog", "macro", "meso", "free"):
        raise HTTPException(422, "process_group must be catalog, macro, meso or free")
    if actor_group not in ("original", "meso", "macro"):
        raise HTTPException(422, "actor_group must be original, meso or macro")
    return {
        "items": aggregates.top_actor_subprocess(
            db,
            category=category,
            limit=limit,
            process_group=process_group,
            actor_group=actor_group,
        )
    }


@router.get("/actor-process-documents")
def dashboard_actor_process_documents(
    process_id: Optional[int] = Query(None, description="ID subprocess из каталога (режим catalog)"),
    process_key: Optional[str] = Query(None, description="Ключ столбца из heatmap (column_keys)"),
    actor: str = Query(..., max_length=4096),
    process_group: str = Query("catalog"),
    actor_group: str = Query("original"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if process_id is None and not process_key:
        raise HTTPException(422, "Укажите process_id или process_key")
    if process_group not in ("catalog", "macro", "meso", "free"):
        raise HTTPException(422, "process_group must be catalog, macro, meso or free")
    if actor_group not in ("original", "meso", "macro"):
        raise HTTPException(422, "actor_group must be original, meso or macro")
    return {
        "items": aggregates.documents_for_actor_process(
            db,
            process_id=process_id,
            process_key=process_key,
            actor=actor,
            actor_group=actor_group,
            process_group=process_group,
            limit=limit,
        )
    }


@router.get("/triples")
def dashboard_triples(
    process_id: int = Query(...),
    limit: int = Query(40, le=200),
    db: Session = Depends(get_db),
):
    return {"items": aggregates.top_triples(db, process_id=process_id, limit=limit)}
