"""
Модуль для извлечения связей между сущностями
"""
import re
from typing import List, Dict, Tuple, Optional
# from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
# import torch


class RelationExtractor:
    """Класс для извлечения связей между сущностями"""
    
    def __init__(self, use_gpu: bool = False):
        self.use_gpu = use_gpu
        # self.device = "mps" if use_gpu and torch.backends.mps.is_available() else "cpu"
        # Используем паттерн-подход для начала, можно расширить LLM
        self._init_patterns()
    
    def _init_patterns(self):
        """Инициализация паттернов для извлечения связей"""
        # Паттерны для типичных бизнес-связей
        self.relation_patterns = [
            (r'(\w+)\s+(?:заключил|заключить|подписал|подписать)\s+(?:договор|контракт|соглашение)\s+(?:с|на)\s+(\w+)', 'заключить_договор'),
            (r'(\w+)\s+(?:поставил|поставить|поставляет|поставка)\s+(\w+)', 'поставить'),
            (r'(\w+)\s+(?:получил|получить|получает)\s+(\w+)', 'получить'),
            (r'(\w+)\s+(?:управляет|управлять|управление)\s+(\w+)', 'управлять'),
            (r'(\w+)\s+(?:работает|работать)\s+(?:с|в)\s+(\w+)', 'работать_с'),
            (r'(\w+)\s+(?:взаимодействует|взаимодействовать)\s+(?:с)\s+(\w+)', 'взаимодействовать_с'),
            (r'(\w+)\s+(?:закупает|закупить|закупка)\s+(\w+)', 'закупить'),
            (r'(\w+)\s+(?:продает|продать|продажа)\s+(\w+)', 'продать'),
            (r'(\w+)\s+(?:отчитывается|отчитаться)\s+(?:перед|в)\s+(\w+)', 'отчитаться'),
            (r'(\w+)\s+(?:контролирует|контролировать)\s+(\w+)', 'контролировать'),
        ]
    
    def extract_relations_pattern(self, text: str, entities: List[Dict]) -> List[Dict]:
        """Извлечение связей на основе паттернов"""
        relations = []
        entity_texts = {e['text']: e for e in entities}
        seen_relations = set()  # Для избежания дубликатов
        
        # Ищем связи между сущностями в тексте
        for pattern, relation_type in self.relation_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                source_text = match.group(1)
                target_text = match.group(2)
                
                # Проверяем, являются ли найденные слова сущностями
                source_entity = self._find_entity(source_text, entity_texts)
                target_entity = self._find_entity(target_text, entity_texts)
                
                if source_entity and target_entity:
                    # Пропускаем связи между одинаковыми сущностями
                    if source_entity['text'].lower() == target_entity['text'].lower():
                        continue
                    
                    # Создаем ключ для проверки дубликатов
                    relation_key = (source_entity['text'].lower(), relation_type, target_entity['text'].lower())
                    if relation_key not in seen_relations:
                        seen_relations.add(relation_key)
                        relations.append({
                            'source': source_entity['text'],
                            'target': target_entity['text'],
                            'relation': relation_type,
                            'source_type': source_entity['type'],
                            'target_type': target_entity['type'],
                            'context': match.group(0)
                        })
        
        # Дополнительно ищем связи через близость сущностей в тексте
        proximity_relations = self._extract_proximity_relations(text, entities)
        
        # Фильтруем дубликаты из proximity relations
        for rel in proximity_relations:
            relation_key = (rel['source'].lower(), rel['relation'], rel['target'].lower())
            if relation_key not in seen_relations:
                seen_relations.add(relation_key)
                relations.append(rel)
        
        return relations
    
    def _find_entity(self, text: str, entity_dict: Dict) -> Optional[Dict]:
        """Находит сущность по тексту (частичное совпадение)"""
        text_lower = text.lower()
        for entity_text, entity in entity_dict.items():
            if text_lower in entity_text.lower() or entity_text.lower() in text_lower:
                return entity
        return None
    
    def _extract_proximity_relations(self, text: str, entities: List[Dict], max_distance: int = 100) -> List[Dict]:
        """Извлечение связей на основе близости сущностей в тексте"""
        relations = []
        
        # Сортируем сущности по позиции в тексте
        sorted_entities = sorted(entities, key=lambda x: x.get('start', 0))
        
        for i in range(len(sorted_entities) - 1):
            source = sorted_entities[i]
            target = sorted_entities[i + 1]
            
            # Пропускаем связи между одинаковыми сущностями
            if source['text'].lower() == target['text'].lower():
                continue
            
            # Проверяем расстояние между сущностями
            source_end = source.get('end', 0)
            target_start = target.get('start', 0)
            
            if 0 < target_start - source_end < max_distance:
                # Извлекаем контекст между сущностями
                context_start = max(0, source_end)
                context_end = min(len(text), target_start + 100)
                context = text[context_start:context_end].strip()
                
                # Пропускаем слишком короткий контекст
                if len(context) < 10:
                    continue
                
                # Определяем тип связи по контексту
                relation_type = self._infer_relation_type(context)
                
                # Пропускаем общие связи, если нет четкого контекста
                if relation_type == 'связан_с' and len(context) < 30:
                    continue
                
                # Проверяем, что связь имеет смысл
                if self._is_valid_relation(source, target, context):
                    relations.append({
                        'source': source['text'],
                        'target': target['text'],
                        'relation': relation_type,
                        'source_type': source['type'],
                        'target_type': target['type'],
                        'context': context[:200]  # Ограничиваем длину контекста
                    })
        
        return relations
    
    def _is_valid_relation(self, source: Dict, target: Dict, context: str) -> bool:
        """Проверяет, является ли связь валидной"""
        context_lower = context.lower()
        
        # Пропускаем связи, где в контексте нет глаголов действия
        action_verbs = ['заключил', 'заключить', 'подписал', 'подписать', 'поставил', 
                        'поставить', 'получил', 'получить', 'управляет', 'управлять',
                        'работает', 'работать', 'закупает', 'закупить', 'продает',
                        'продать', 'отчитывается', 'контролирует', 'контролировать',
                        'взаимодействует', 'взаимодействовать', 'сотрудничает']
        
        has_action = any(verb in context_lower for verb in action_verbs)
        
        # Если нет глагола действия, но есть предлоги/союзы, это может быть валидная связь
        connecting_words = ['с', 'для', 'от', 'к', 'в', 'на', 'по', 'и', 'или']
        has_connection = any(word in context_lower for word in connecting_words)
        
        return has_action or (has_connection and len(context) > 20)
    
    def _infer_relation_type(self, context: str) -> Optional[str]:
        """Определяет тип связи по контексту"""
        context_lower = context.lower()
        
        relation_keywords = {
            'заключить_договор': ['договор', 'контракт', 'соглашение', 'подписать'],
            'поставить': ['поставка', 'поставить', 'доставить', 'отгрузить'],
            'закупить': ['закупка', 'закупить', 'приобрести', 'купить'],
            'управлять': ['управление', 'управлять', 'руководить', 'контролировать'],
            'работать_с': ['работа', 'сотрудничество', 'взаимодействие'],
            'отчитаться': ['отчет', 'отчитаться', 'предоставить отчет'],
        }
        
        for relation_type, keywords in relation_keywords.items():
            if any(keyword in context_lower for keyword in keywords):
                return relation_type
        
        return 'связан_с'  # Общая связь по умолчанию
    
    def extract(self, text: str, entities: List[Dict]) -> List[Dict]:
        """Основной метод извлечения связей"""
        return self.extract_relations_pattern(text, entities)
