"""
Модуль для чтения документов различных форматов
"""
import docx
import pdfplumber
from pathlib import Path
from typing import Optional


class DocumentReader:
    """Класс для чтения документов разных форматов"""
    
    @staticmethod
    def read_docx(file_path: Path) -> str:
        """Читает DOCX файл и возвращает текст"""
        try:
            doc = docx.Document(file_path)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            return text
        except Exception as e:
            raise Exception(f"Ошибка чтения DOCX файла {file_path}: {str(e)}")
    
    @staticmethod
    def read_pdf(file_path: Path) -> str:
        """Читает PDF файл и возвращает текст"""
        try:
            text = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text
        except Exception as e:
            raise Exception(f"Ошибка чтения PDF файла {file_path}: {str(e)}")
    
    @staticmethod
    def read_txt(file_path: Path) -> str:
        """Читает TXT файл и возвращает текст"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            raise Exception(f"Ошибка чтения TXT файла {file_path}: {str(e)}")
    
    @classmethod
    def read_document(cls, file_path: Path) -> Optional[str]:
        """Читает документ любого поддерживаемого формата"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Файл не найден: {file_path}")
        
        suffix = file_path.suffix.lower()
        
        if suffix == '.docx':
            return cls.read_docx(file_path)
        elif suffix == '.pdf':
            return cls.read_pdf(file_path)
        elif suffix == '.txt':
            return cls.read_txt(file_path)
        else:
            raise ValueError(f"Неподдерживаемый формат файла: {suffix}")
