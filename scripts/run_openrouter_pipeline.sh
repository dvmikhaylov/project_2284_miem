#!/bin/bash
# Запуск OpenRouter-пайплайна на validate_data/.
# Результат: output/openrouter/
cd "$(dirname "$0")/.."
[ -f key.sh ] && source key.sh
exec python3 -m NLP.openrouter_pipeline.run --dir validate_data --output output/openrouter
