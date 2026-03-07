"""
Этап 1: чтение документов (PDF, DOCX, TXT)
"""
import docx
import pdfplumber
from pathlib import Path
from typing import Optional


def read_document(file_path: Path) -> Optional[str]:
    """Читает документ и возвращает текст."""
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Файл не найден: {file_path}")
    
    suffix = file_path.suffix.lower()
    if suffix == ".docx":
        doc = docx.Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs)
    if suffix == ".pdf":
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
        return text
    if suffix == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    raise ValueError(f"Неподдерживаемый формат: {suffix}")
