from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ProcessCatalog
from ..schemas import CatalogProcessItem
from ..services.catalog_sync import sync_process_catalog

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])


@router.post("/sync")
def catalog_sync(db: Session = Depends(get_db)):
    n = sync_process_catalog(db)
    return {"updated_rows": n}


@router.get("/processes", response_model=List[CatalogProcessItem])
def list_processes(db: Session = Depends(get_db)):
    rows = db.execute(select(ProcessCatalog).order_by(ProcessCatalog.catalog_index)).scalars().all()
    return [
        CatalogProcessItem(
            id=r.id,
            category=r.category,
            process_name=r.process_name,
            priority=r.priority,
            priority_raw=r.priority_raw,
        )
        for r in rows
    ]
