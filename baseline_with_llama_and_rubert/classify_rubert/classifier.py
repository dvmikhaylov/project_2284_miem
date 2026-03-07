"""
Этап 4: zero-shot классификация текста в бизнес-процессы через RuBERT.

Используется подход: эмбеддинги текста и меток (названия процессов),
ближайшая метка по косинусной близости.
"""
import json
from pathlib import Path
from typing import List, Dict, Tuple

from ..config import BUSINESS_PROCESSES_JSON, RUBERT_MODEL


def _load_labels() -> List[Dict]:
    with open(BUSINESS_PROCESSES_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def classify_zero_shot(text: str, top_k: int = 5) -> Dict:
    """
    Классифицирует текст в один из бизнес-процессов (zero-shot через RuBERT).
    Возвращает: category, subprocess (process), number (index), confidence, alternatives.
    """
    labels_data = _load_labels()
    labels = [item["process"] for item in labels_data]
    
    try:
        from transformers import AutoTokenizer, AutoModel
        import torch
    except ImportError:
        # Fallback: возвращаем первый процесс с низкой уверенностью
        return {
            "category": labels_data[0]["category"],
            "subprocess": labels_data[0]["process"],
            "number": 0,
            "confidence": 0.0,
            "alternatives": [{"process": d["process"], "category": d["category"], "score": 0.0} for d in labels_data[1:top_k]],
        }
    
    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(RUBERT_MODEL)
    model = AutoModel.from_pretrained(RUBERT_MODEL)
    model.to(device)
    model.eval()
    
    def embed(s: str):
        inp = tokenizer(s, padding=True, truncation=True, max_length=512, return_tensors="pt")
        inp = {k: v.to(device) for k, v in inp.items()}
        with torch.no_grad():
            out = model(**inp)
        # [CLS] или mean pooling
        return out.last_hidden_state[:, 0, :].cpu().numpy().squeeze()
    
    # Эмбеддинг текста (обрезаем для длинных документов)
    text_short = text[:4000] if len(text) > 4000 else text
    text_emb = embed(text_short)
    
    # Эмбеддинги меток (названия процессов)
    label_embs = []
    for label in labels:
        label_embs.append(embed(label))
    
    import numpy as np
    text_emb = np.atleast_2d(text_emb)
    label_matrix = np.vstack(label_embs)
    # Косинусная близость
    norms = np.linalg.norm(label_matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1
    label_matrix = label_matrix / norms
    text_norm = text_emb / (np.linalg.norm(text_emb) or 1)
    scores = (text_norm @ label_matrix.T).squeeze()
    if scores.ndim == 0:
        scores = np.array([scores])
    
    top_indices = np.argsort(scores)[::-1][:top_k]
    best_idx = int(top_indices[0])
    best_score = float(scores[best_idx])
    # Нормализуем в [0, 1] (cosine может быть отрицательным)
    confidence = (best_score + 1) / 2.0 if best_score <= 1 else min(1.0, best_score)
    
    best = labels_data[best_idx]
    alternatives = [
        {
            "number": int(idx),
            "process": labels_data[int(idx)]["process"],
            "category": labels_data[int(idx)]["category"],
            "score": float(scores[int(idx)]),
        }
        for idx in top_indices[1:top_k]
    ]
    
    return {
        "category": best["category"],
        "subprocess": best["process"],
        "number": best_idx,
        "confidence": round(confidence, 4),
        "alternatives": alternatives,
    }
