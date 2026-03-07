#!/bin/bash
# Запуск пайплайна OpenRouter (один вызов LLM на документ) на validate_data/.
# Результат: output/exp_llama_relations/
cd "$(dirname "$0")/.."
[ -f key.sh ] && source key.sh
exec ./venv/bin/python -m experiments.exp_llama_relations.run --dir validate_data
