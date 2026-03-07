"""
Модуль для извлечения именованных сущностей (NER) — baseline
"""
from typing import List, Dict, Optional
import spacy
from natasha import (
    Segmenter,
    MorphVocab,
    NewsEmbedding,
    NewsMorphTagger,
    NewsNERTagger,
    Doc
)


class NERExtractor:
    """Класс для извлечения именованных сущностей из русского текста"""
    
    def __init__(self, model_type: str = "natasha", use_gpu: bool = False):
        self.model_type = model_type
        self.use_gpu = use_gpu
        
        if model_type == "natasha":
            self._init_natasha()
        elif model_type == "spacy":
            self._init_spacy()
        else:
            raise ValueError(f"Неподдерживаемый тип модели: {model_type}")
    
    def _init_natasha(self):
        self.segmenter = Segmenter()
        self.morph_vocab = MorphVocab()
        self.emb = NewsEmbedding()
        self.morph_tagger = NewsMorphTagger(self.emb)
        self.ner_tagger = NewsNERTagger(self.emb)
    
    def _init_spacy(self):
        try:
            self.nlp = spacy.load("ru_core_news_md")
        except OSError:
            raise OSError(
                "Модель ru_core_news_md не установлена. "
                "Установите: python -m spacy download ru_core_news_md"
            )
    
    def extract_entities_natasha(self, text: str) -> List[Dict]:
        doc = Doc(text)
        doc.segment(self.segmenter)
        doc.tag_morph(self.morph_tagger)
        doc.tag_ner(self.ner_tagger)
        
        entities = []
        for span in doc.spans:
            if span.type in ['PER', 'ORG', 'LOC']:
                entity_text = span.text.strip()
                if len(entity_text) < 2:
                    continue
                if self._is_invalid_entity(entity_text, span.type):
                    continue
                entities.append({
                    'text': entity_text,
                    'type': span.type,
                    'start': span.start,
                    'end': span.stop,
                    'confidence': 1.0
                })
        return entities
    
    def _is_invalid_entity(self, text: str, entity_type: str) -> bool:
        text_lower = text.lower().strip()
        invalid_patterns = {
            'PER': ['договор', 'доверенность', 'стороны', 'подрядчик', 'заказчик',
                    'исполнитель', 'сторона', 'договоре', 'договора', 'договору',
                    'согласование', 'согласования', 'согласованию'],
            'ORG': ['договор', 'доверенность', 'стороны', 'договоре', 'договора',
                    'согласование', 'согласования', 'согласованию', 'лист'],
            'LOC': ['договор', 'доверенность', 'согласование']
        }
        if entity_type in invalid_patterns:
            for pattern in invalid_patterns[entity_type]:
                if pattern in text_lower:
                    return True
        if text.replace(' ', '').replace('-', '').replace('.', '').isdigit():
            return True
        if text_lower in ['согласование', 'согласования', 'лист', 'страница', 'документ']:
            return True
        return False
    
    def extract_entities_spacy(self, text: str) -> List[Dict]:
        doc = self.nlp(text)
        entities = []
        for ent in doc.ents:
            entity_type = ent.label_
            if entity_type in ['PER', 'ORG', 'LOC', 'MISC']:
                entity_text = ent.text.strip()
                if len(entity_text) < 2:
                    continue
                if self._is_invalid_entity(entity_text, entity_type):
                    continue
                entities.append({
                    'text': entity_text,
                    'type': entity_type,
                    'start': ent.start_char,
                    'end': ent.end_char,
                    'confidence': 1.0
                })
        return entities
    
    def extract(self, text: str) -> List[Dict]:
        if self.model_type == "natasha":
            return self.extract_entities_natasha(text)
        elif self.model_type == "spacy":
            return self.extract_entities_spacy(text)
        else:
            raise ValueError(f"Неподдерживаемый тип модели: {self.model_type}")
