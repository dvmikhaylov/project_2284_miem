"""
Основной пайплайн для извлечения информации из документов (baseline)
"""
import json
from pathlib import Path
from typing import Dict, List, Optional

from .document_reader import DocumentReader
from .ner_extractor import NERExtractor
from .relation_extractor import RelationExtractor
from .process_classifier import ProcessClassifier
from .business_process_loader import BusinessProcessLoader
from .config import USE_GPU, NER_MODEL, MAX_TEXT_LENGTH, CHUNK_SIZE, BUSINESS_PROCESSES_FILE


class DocumentPipeline:
    """Основной пайплайн обработки документов"""
    
    def __init__(self):
        self.doc_reader = DocumentReader()
        self.ner_extractor = NERExtractor(model_type=NER_MODEL, use_gpu=USE_GPU)
        self.relation_extractor = RelationExtractor(use_gpu=USE_GPU)
        self.bp_loader = BusinessProcessLoader(BUSINESS_PROCESSES_FILE)
        self.process_classifier = ProcessClassifier(self.bp_loader, use_gpu=USE_GPU)
    
    def _chunk_text(self, text: str) -> List[str]:
        if len(text) <= MAX_TEXT_LENGTH:
            return [text]
        chunks = []
        words = text.split()
        current_chunk = []
        current_length = 0
        for word in words:
            word_length = len(word) + 1
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
        chains = []
        relation_map = {}
        for rel in relations:
            source = rel['source']
            if source not in relation_map:
                relation_map[source] = []
            relation_map[source].append(rel)
        for entity in entities:
            entity_text = entity['text']
            if entity_text in relation_map:
                for rel in relation_map[entity_text]:
                    chains.append([entity_text, rel['relation'], rel['target']])
        return chains
    
    def process_document(self, file_path: Path) -> Dict:
        text = self.doc_reader.read_document(file_path)
        if not text or len(text.strip()) == 0:
            return {'error': 'Документ пуст или не удалось извлечь текст'}
        
        chunks = self._chunk_text(text)
        all_entities = []
        for chunk in chunks:
            entities = self.ner_extractor.extract(chunk)
            all_entities.extend(entities)
        
        unique_entities = {}
        for entity in all_entities:
            normalized_text = ' '.join(entity['text'].split())
            key = normalized_text.lower().strip()
            if len(key) < 2:
                continue
            if key not in unique_entities or len(normalized_text) > len(unique_entities[key]['text']):
                entity['text'] = normalized_text
                unique_entities[key] = entity
        entities_list = list(unique_entities.values())
        
        all_relations = []
        for chunk in chunks:
            relations = self.relation_extractor.extract(chunk, entities_list)
            all_relations.extend(relations)
        unique_relations = {}
        for rel in all_relations:
            key = f"{rel['source']}_{rel['relation']}_{rel['target']}".lower()
            if key not in unique_relations:
                unique_relations[key] = rel
        relations_list = list(unique_relations.values())
        
        classification = self.process_classifier.classify(text)
        chains = self._build_relation_chains(entities_list, relations_list)
        
        return {
            'document': str(file_path.name),
            'entities': [{'text': e['text'], 'type': e['type'], 'id': i} for i, e in enumerate(entities_list)],
            'relations': [
                {
                    'source': r['source'], 'target': r['target'], 'relation': r['relation'],
                    'source_type': r.get('source_type', 'UNK'), 'target_type': r.get('target_type', 'UNK'),
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
    
    def process_and_save(self, file_path: Path, output_path: Optional[Path] = None) -> Dict:
        result = self.process_document(file_path)
        if output_path is None:
            from .config import OUTPUT_DIR
            output_path = OUTPUT_DIR / f"{Path(file_path).stem}_result.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return result
