import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import PROJECT_ROOT
from ..models import ProcessCatalog

BUSINESS_JSON = PROJECT_ROOT / "business_processes" / "business_processes.json"

PLACEHOLDER_CATEGORY = "(извлечено)"
PLACEHOLDER_PROCESS = "— вне каталога —"


def ensure_placeholder_process(db: Session) -> ProcessCatalog:
    row = db.execute(
        select(ProcessCatalog).where(
            ProcessCatalog.category == PLACEHOLDER_CATEGORY,
            ProcessCatalog.process_name == PLACEHOLDER_PROCESS,
        )
    ).scalars().first()
    if row:
        return row
    mx = db.scalar(select(func.max(ProcessCatalog.catalog_index)))
    nxt = (int(mx) + 1) if mx is not None else 999999
    row = ProcessCatalog(
        category=PLACEHOLDER_CATEGORY,
        process_name=PLACEHOLDER_PROCESS,
        priority_raw=1,
        priority=0.01,
        catalog_index=nxt,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def sync_process_catalog(db: Session) -> int:
    if not BUSINESS_JSON.exists():
        ensure_placeholder_process(db)
        return 0
    with open(BUSINESS_JSON, "r", encoding="utf-8") as f:
        rows = json.load(f)
    max_p = max(int(x.get("priority", 1) or 1) for x in rows) if rows else 1
    count = 0
    for i, p in enumerate(rows):
        cat = p.get("category") or ""
        name = p.get("process") or ""
        raw = int(p.get("priority", 1) or 1)
        pnorm = round(raw / max_p, 8) if max_p else 1.0
        existing = db.execute(
            select(ProcessCatalog).where(
                ProcessCatalog.category == cat,
                ProcessCatalog.process_name == name,
            )
        ).scalars().first()
        if existing:
            existing.priority_raw = raw
            existing.priority = float(pnorm)
            existing.catalog_index = i
        else:
            db.add(
                ProcessCatalog(
                    category=cat,
                    process_name=name,
                    priority_raw=raw,
                    priority=float(pnorm),
                    catalog_index=i,
                )
            )
        count += 1
    db.commit()
    ensure_placeholder_process(db)
    return count
