"""Чтение docx/pdf/txt и подготовка плоского текста для NLP (OpenRouter получает только текст)."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

import docx
import pdfplumber
from docx.document import Document as DocxDocument
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph


def _iter_docx_body_blocks(document: DocxDocument):
    """Параграфы и таблицы в порядке следования в документе (не только «голые» параграфы)."""
    body = document.element.body
    for child in body:
        if child.tag == qn("w:p"):
            yield Paragraph(child, document)
        elif child.tag == qn("w:tbl"):
            yield Table(child, document)


class DocumentReader:
    @staticmethod
    def read_docx(file_path: Path) -> str:
        """DOCX → текст: параграфы и ячейки таблиц в порядке документа."""
        try:
            doc = docx.Document(file_path)
            parts: List[str] = []
            for block in _iter_docx_body_blocks(doc):
                if isinstance(block, Paragraph):
                    t = (block.text or "").strip()
                    if t:
                        parts.append(t)
                else:
                    for row in block.rows:
                        cells = [(c.text or "").strip() for c in row.cells]
                        line = " | ".join(x for x in cells if x)
                        if line:
                            parts.append(line)
            return "\n".join(parts)
        except Exception as e:
            raise Exception(f"Ошибка чтения DOCX файла {file_path}: {e}") from e

    @staticmethod
    def read_docx_via_pdf(file_path: Path) -> str:
        """
        DOCX → PDF (LibreOffice) → текст через pdfplumber.
        Нужен `soffice` или `libreoffice` в PATH. Включается переменной DOCX_READ_VIA_PDF=1
        или если обычное чтение дало слишком мало текста и DOCX_FALLBACK_LIBREOFFICE=1 (по умолчанию да).
        """
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if not soffice:
            raise RuntimeError(
                "DOCX→PDF: не найден LibreOffice (исполняемый файл soffice или libreoffice в PATH)."
            )
        outdir = tempfile.mkdtemp(prefix="docx2pdf_")
        timeout = int(os.environ.get("LIBREOFFICE_CONVERT_TIMEOUT", "180"))
        try:
            cp = subprocess.run(
                [soffice, "--headless", "--convert-to", "pdf", "--outdir", outdir, str(file_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if cp.returncode != 0:
                err = (cp.stderr or cp.stdout or "").strip()[:800]
                raise RuntimeError(f"LibreOffice завершился с кодом {cp.returncode}: {err}")
            pdf_path = Path(outdir) / (file_path.stem + ".pdf")
            if not pdf_path.exists():
                raise RuntimeError(f"После конвертации не найден файл: {pdf_path}")
            return DocumentReader.read_pdf(pdf_path)
        finally:
            shutil.rmtree(outdir, ignore_errors=True)

    @staticmethod
    def read_pdf(file_path: Path) -> str:
        try:
            text = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text
        except Exception as e:
            raise Exception(f"Ошибка чтения PDF файла {file_path}: {e}") from e

    @staticmethod
    def read_txt(file_path: Path) -> str:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            raise Exception(f"Ошибка чтения TXT файла {file_path}: {e}") from e

    @classmethod
    def read_document(cls, file_path: Path) -> Optional[str]:
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Файл не найден: {file_path}")
        suffix = file_path.suffix.lower()
        if suffix == ".docx":
            via_pdf = os.environ.get("DOCX_READ_VIA_PDF", "").strip().lower() in (
                "1",
                "true",
                "yes",
            )
            if via_pdf:
                return cls.read_docx_via_pdf(file_path)
            text = cls.read_docx(file_path)
            fallback = os.environ.get("DOCX_FALLBACK_LIBREOFFICE", "1").strip().lower() not in (
                "0",
                "false",
                "no",
            )
            if fallback and len(text.strip()) < int(os.environ.get("DOCX_FALLBACK_MIN_CHARS", "40")):
                try:
                    alt = cls.read_docx_via_pdf(file_path)
                    if len(alt.strip()) > len(text.strip()):
                        return alt
                except Exception:
                    pass
            return text
        if suffix == ".pdf":
            return cls.read_pdf(file_path)
        if suffix == ".txt":
            return cls.read_txt(file_path)
        raise ValueError(f"Неподдерживаемый формат файла: {suffix}")
