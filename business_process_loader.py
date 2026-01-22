"""
Модуль для загрузки и парсинга бизнес-процессов
"""
from pathlib import Path
from typing import Dict, List, Tuple
import re


class BusinessProcessLoader:
    """Класс для загрузки и структурирования бизнес-процессов"""
    
    def __init__(self, file_path: Path):
        self.file_path = Path(file_path)
        self.processes = []
        self.process_map = {}  # Маппинг номер -> (категория, подпроцесс)
        self._load_processes()
    
    def _load_processes(self):
        """Загружает бизнес-процессы из файла"""
        with open(self.file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        current_category = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Проверяем, является ли строка категорией (без номера)
            if not re.match(r'^\d+\.', line):
                # Это категория
                current_category = line
                continue
            
            # Это подпроцесс с номером
            match = re.match(r'^(\d+)\.\s*(.+)$', line)
            if match:
                number = int(match.group(1))
                subprocess = match.group(2)
                
                self.processes.append({
                    'number': number,
                    'category': current_category,
                    'subprocess': subprocess,
                    'full_name': f"{current_category} - {subprocess}"
                })
                
                self.process_map[number] = (current_category, subprocess)
    
    def get_all_processes(self) -> List[Dict]:
        """Возвращает список всех бизнес-процессов"""
        return self.processes
    
    def get_process_by_number(self, number: int) -> Tuple[str, str]:
        """Возвращает категорию и подпроцесс по номеру"""
        return self.process_map.get(number, (None, None))
    
    def get_processes_text(self) -> str:
        """Возвращает текст всех процессов для промпта"""
        lines = []
        for proc in self.processes:
            lines.append(f"{proc['number']}. {proc['full_name']}")
        return "\n".join(lines)
