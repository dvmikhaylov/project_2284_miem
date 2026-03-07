# Эксперименты пайплайна

В проекте два подхода: **baseline** и **OpenRouter**.

## Запуск

Из корня проекта:

```bash
# Оба подхода на validate_data/
python -m experiments.run_all

# Только OpenRouter (с ключом: source key.sh)
python -m experiments.exp_llama_relations.run
python -m experiments.exp_llama_relations.run --dir validate_data --output output/exp_llama_relations
python -m experiments.exp_llama_relations.run --file validate_data/Договор.docx
```

Результаты: `output/baseline/` (baseline) и `output/exp_llama_relations/` (OpenRouter).
