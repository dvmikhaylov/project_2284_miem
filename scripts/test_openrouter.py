#!/usr/bin/env python3
"""
Проверка вызова OpenRouter (gpt-oss-120b:free): промпт + ответ.
Запуск: source key.sh && python scripts/test_openrouter.py
"""
import os
import sys
from pathlib import Path

# Подгрузить ключ из key.sh если не в env
if not os.environ.get("OPENROUTER_API_KEY"):
    key_file = Path(__file__).resolve().parent.parent / "key.sh"
    if key_file.exists():
        with open(key_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("export "):
                    line = line[7:]
                if line.startswith("OPENROUTER_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip("'\"")
                    os.environ["OPENROUTER_API_KEY"] = key
                    break

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from baseline_with_llama_and_rubert.openrouter_client import call_openrouter
from baseline_with_llama_and_rubert.config import OPENROUTER_API_KEY, OPENROUTER_MODEL

SAMPLE_TEXT = """АО «ВДНХ» и ООО «Рога и копыта» заключили договор. Директор Иванов И.И. подписал документ. Москва."""


def main():
    if not OPENROUTER_API_KEY:
        print("OPENROUTER_API_KEY не задан. Запустите: source key.sh")
        sys.exit(1)
    print("Модель:", OPENROUTER_MODEL)
    print()
    prompt = """Извлеки из текста именованные сущности: персоны (PER), организации (ORG), локации (LOC).
Используй только типы PER, ORG, LOC. Ответ — только JSON-массив объектов с полями "text" и "type".
Пример: [{"text": "АО ВДНХ", "type": "ORG"}, {"text": "Иванов И.И.", "type": "PER"}]

Текст:
""" + SAMPLE_TEXT + """

Ответ — только массив JSON, без markdown:"""
    print("--- Промпт (NER) ---")
    print(prompt)
    print("--- Конец промпта ---")
    print()
    try:
        resp = call_openrouter(
            prompt,
            api_key=OPENROUTER_API_KEY,
            model=OPENROUTER_MODEL,
            max_tokens=400,
            temperature=0.0,
        )
    except Exception as e:
        print("Ошибка вызова API:", e)
        sys.exit(1)
    if resp is None:
        print("Ответ пустой (возможен 429 rate limit — подождите и повторите).")
        sys.exit(1)
    if not resp.strip():
        print("Ответ пустой.")
        sys.exit(1)
    print("--- Ответ 120b ---")
    print(resp)
    print("--- Конец ответа ---")
    print("OK: вызов OpenRouter прошёл успешно.")


if __name__ == "__main__":
    main()
