"""
Модуль для классификации текста в бизнес-процессы
"""
import re
from typing import List, Dict, Tuple, Optional
# from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
# import torch
from business_process_loader import BusinessProcessLoader


class ProcessClassifier:
    """Класс для классификации текста в бизнес-процессы"""
    
    def __init__(self, business_process_loader: BusinessProcessLoader, use_gpu: bool = False):
        self.bp_loader = business_process_loader
        self.use_gpu = use_gpu
        # self.device = "mps" if use_gpu and torch.backends.mps.is_available() else "cpu"
        self._init_keywords()
    
    def _init_keywords(self):
        """Инициализация ключевых слов для каждого бизнес-процесса"""
        self.keyword_map = {}
        
        # Маппинг ключевых слов на номера процессов
        keyword_mappings = {
            # Закупки
            'закупк': [81, 82, 83, 84, 38, 39],
            'тендер': [82],
            'поставщик': [39, 83],
            'контракт': [83, 84, 24, 76],
            'договор': [24, 76, 83, 84],
            
            # Финансы
            'финанс': [46, 47, 48, 49, 50, 51, 52],
            'бюджет': [46],
            'бухгалтер': [50],
            'налог': [51],
            'отчетност': [52],
            
            # Персонал
            'персонал': [56, 57, 58, 59, 60, 61, 62],
            'сотрудник': [57, 58, 59, 60],
            'подбор': [57],
            'обучение': [59],
            'кадр': [62],
            
            # Продажи
            'продаж': [19, 20, 21, 22, 23, 24, 25],
            'клиент': [25, 26, 27, 28, 29, 30, 31, 32],
            'заявк': [20],
            'коммерческ': [23],
            
            # IT
            'it': [66, 67, 68, 69, 70, 71, 72, 73, 74, 75],
            'систем': [74, 75],
            'разработк': [69, 76],
            'безопасност': [68],
            
            # Юридические
            'юридическ': [76, 77, 78],
            'претензи': [78],
            'комплаенс': [79],
            
            # Производство
            'производств': [36, 37, 38, 39, 40, 41, 42, 43, 44, 45],
            'склад': [40, 41],
            'логистик': [40],
            'качеств': [42],
        }
        
        self.keyword_map = keyword_mappings
    
    def classify_by_keywords(self, text: str) -> List[Tuple[int, float]]:
        """Классификация на основе ключевых слов"""
        text_lower = text.lower()
        scores = {}
        
        for keyword, process_numbers in self.keyword_map.items():
            if keyword in text_lower:
                for proc_num in process_numbers:
                    scores[proc_num] = scores.get(proc_num, 0) + 1
        
        # Сортируем по убыванию score
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_scores[:5]  # Топ-5 процессов
    
    def classify(self, text: str) -> Dict:
        """Основной метод классификации"""
        # Используем keyword-based классификацию
        top_processes = self.classify_by_keywords(text)
        
        if not top_processes:
            # Если не найдено, возвращаем общий процесс
            return {
                'category': 'Общие процессы',
                'subprocess': 'Не определен',
                'number': None,
                'confidence': 0.0
            }
        
        # Берем топ-1 процесс
        top_number, score = top_processes[0]
        category, subprocess = self.bp_loader.get_process_by_number(top_number)
        
        # Нормализуем confidence (максимальный score = 5)
        confidence = min(score / 5.0, 1.0)
        
        return {
            'category': category or 'Не определен',
            'subprocess': subprocess or 'Не определен',
            'number': top_number,
            'confidence': confidence,
            'alternatives': [
                {
                    'number': num,
                    'category': self.bp_loader.get_process_by_number(num)[0],
                    'subprocess': self.bp_loader.get_process_by_number(num)[1],
                    'score': sc
                }
                for num, sc in top_processes[1:3]  # Следующие 2 альтернативы
            ]
        }
