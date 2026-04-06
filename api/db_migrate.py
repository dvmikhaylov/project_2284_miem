from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def apply_sqlite_migrations(engine: Engine) -> None:
    url = str(engine.url)
    if not url.startswith("sqlite"):
        return
    insp = inspect(engine)
    if not insp.has_table("document_process_matches"):
        return
    cols = {c["name"] for c in insp.get_columns("document_process_matches")}
    stmts = []
    if "process_free_label" not in cols:
        stmts.append("ALTER TABLE document_process_matches ADD COLUMN process_free_label TEXT")
    if "process_meso" not in cols:
        stmts.append("ALTER TABLE document_process_matches ADD COLUMN process_meso VARCHAR(512)")
    if "process_macro" not in cols:
        stmts.append("ALTER TABLE document_process_matches ADD COLUMN process_macro VARCHAR(256)")
    if not stmts:
        return
    with engine.begin() as conn:
        for s in stmts:
            conn.execute(text(s))
