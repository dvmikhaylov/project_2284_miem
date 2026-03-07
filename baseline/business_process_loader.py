"""
Модуль для загрузки и парсинга бизнес-процессов (baseline)
"""
from pathlib import Path
from typing import Dict, List, Tuple
import re


class BusinessProcessLoader:
    """Класс для загрузки и структурирования бизнес-процессов из .txt"""
    
    def __init__(self, file_path: Path):
        self.file_path = Path(file_path)
        self.processes = []
        self.process_map = {}
        self._load_processes()
    
    def _load_processes(self):
        with open(self.file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        current_category = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if not re.match(r'^\d+\.', line):
                current_category = line
                continue
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
        return self.processes
    
    def get_process_by_number(self, number: int) -> Tuple[str, str]:
        return self.process_map.get(number, (None, None))
    
    def get_processes_text(self) -> str:
        lines = [f"{p['number']}. {p['full_name']}" for p in self.processes]
        return "\n".join(lines)
