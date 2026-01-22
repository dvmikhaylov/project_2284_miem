"""
Основной пайплайн для извлечения информации из документов
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from document_reader import DocumentReader
from ner_extractor import NERExtractor
from relation_extractor import RelationExtractor
from process_classifier import ProcessClassifier
from business_process_loader import BusinessProcessLoader
from config import USE_GPU, NER_MODEL, MAX_TEXT_LENGTH, CHUNK_SIZE


class DocumentPipeline:
    """Основной пайплайн обработки документов"""
    
    def __init__(self):
        # Инициализация компонентов
        self.doc_reader = DocumentReader()
        self.ner_extractor = NERExtractor(model_type=NER_MODEL, use_gpu=USE_GPU)
        self.relation_extractor = RelationExtractor(use_gpu=USE_GPU)
        
        # Загружаем бизнес-процессы
        from config import BUSINESS_PROCESSES_FILE
        self.bp_loader = BusinessProcessLoader(BUSINESS_PROCESSES_FILE)
        self.process_classifier = ProcessClassifier(self.bp_loader, use_gpu=USE_GPU)
    
    def _chunk_text(self, text: str) -> List[str]:
        """Разбивает текст на чанки для обработки"""
        if len(text) <= MAX_TEXT_LENGTH:
            return [text]
        
        chunks = []
        words = text.split()
        current_chunk = []
        current_length = 0
        
        for word in words:
            word_length = len(word) + 1  # +1 для пробела
            if current_length + word_length > CHUNK_SIZE:
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                current_chunk = [word]
                current_length = word_length
            else:
                current_chunk.append(word)
                current_length += word_length
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    def _build_relation_chains(self, entities: List[Dict], relations: List[Dict]) -> List[List[str]]:
        """Строит цепочки связей между сущностями"""
        chains = []
        
        # Создаем граф связей
        entity_map = {e['text']: e for e in entities}
        relation_map = {}
        
        for rel in relations:
            source = rel['source']
            if source not in relation_map:
                relation_map[source] = []
            relation_map[source].append(rel)
        
        # Строим цепочки от каждой сущности
        for entity in entities:
            entity_text = entity['text']
            if entity_text in relation_map:
                for rel in relation_map[entity_text]:
                    chain = [
                        entity_text,
                        rel['relation'],
                        rel['target']
                    ]
                    chains.append(chain)
        
        return chains
    
    def process_document(self, file_path: Path) -> Dict:
        """Обрабатывает документ и возвращает структурированную информацию"""
        # 1. Читаем документ
        text = self.doc_reader.read_document(file_path)
        
        if not text or len(text.strip()) == 0:
            return {
                'error': 'Документ пуст или не удалось извлечь текст'
            }
        
        # 2. Разбиваем на чанки если нужно
        chunks = self._chunk_text(text)
        
        # 3. Извлекаем сущности
        all_entities = []
        for chunk in chunks:
            entities = self.ner_extractor.extract(chunk)
            all_entities.extend(entities)
        
        # Удаляем дубликаты сущностей и нормализуем
        unique_entities = {}
        for entity in all_entities:
            # Нормализуем текст (убираем лишние пробелы, переносы строк)
            normalized_text = ' '.join(entity['text'].split())
            key = normalized_text.lower().strip()
            
            # Пропускаем слишком короткие после нормализации
            if len(key) < 2:
                continue
            
            # Если сущность уже есть, выбираем более полную версию
            if key not in unique_entities:
                entity['text'] = normalized_text
                unique_entities[key] = entity
            else:
                # Если новая версия длиннее, заменяем
                if len(normalized_text) > len(unique_entities[key]['text']):
                    entity['text'] = normalized_text
                    unique_entities[key] = entity
        
        entities_list = list(unique_entities.values())
        
        # 4. Извлекаем связи
        all_relations = []
        for chunk in chunks:
            relations = self.relation_extractor.extract(chunk, entities_list)
            all_relations.extend(relations)
        
        # Удаляем дубликаты связей
        unique_relations = {}
        for rel in all_relations:
            key = f"{rel['source']}_{rel['relation']}_{rel['target']}"
            if key.lower() not in unique_relations:
                unique_relations[key.lower()] = rel
        
        relations_list = list(unique_relations.values())
        
        # 5. Классифицируем в бизнес-процессы
        classification = self.process_classifier.classify(text)
        
        # 6. Строим цепочки связей
        chains = self._build_relation_chains(entities_list, relations_list)
        
        # 7. Формируем результат
        result = {
            'document': str(file_path.name),
            'entities': [
                {
                    'text': e['text'],
                    'type': e['type'],
                    'id': i
                }
                for i, e in enumerate(entities_list)
            ],
            'relations': [
                {
                    'source': r['source'],
                    'target': r['target'],
                    'relation': r['relation'],
                    'source_type': r.get('source_type', 'UNK'),
                    'target_type': r.get('target_type', 'UNK'),
                    'context': r.get('context', '')
                }
                for r in relations_list
            ],
            'relation_chains': chains,
            'business_process': {
                'category': classification['category'],
                'subprocess': classification['subprocess'],
                'number': classification['number'],
                'confidence': classification['confidence'],
                'alternatives': classification.get('alternatives', [])
            },
            'statistics': {
                'total_entities': len(entities_list),
                'total_relations': len(relations_list),
                'total_chains': len(chains),
                'text_length': len(text)
            }
        }
        
        return result
    
    def process_and_save(self, file_path: Path, output_path: Optional[Path] = None) -> Dict:
        """Обрабатывает документ и сохраняет результат в JSON"""
        result = self.process_document(file_path)
        
        if output_path is None:
            from config import OUTPUT_DIR
            output_path = OUTPUT_DIR / f"{Path(file_path).stem}_result.json"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        return result
