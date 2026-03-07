#!/usr/bin/env python3
"""
Единая точка входа: два подхода — baseline и OpenRouter.

  python run.py --baseline [--file PATH] [--dir PATH] [--output DIR]
  python run.py --openrouter [--file PATH] [--dir PATH] [--output DIR]

Без --file/--dir обрабатываются документы из validate_data/.
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description="Пайплайн: извлечение сущностей, связей и бизнес-процесса из документов")
    approach = parser.add_mutually_exclusive_group(required=True)
    approach.add_argument("--baseline", action="store_true", help="Baseline: NER (Natasha), паттерны, классификация по ключевым словам")
    approach.add_argument("--openrouter", action="store_true", help="OpenRouter: один вызов LLM на документ (платная модель по умолчанию)")
    parser.add_argument("--file", type=str, help="Один файл (docx/pdf/txt)")
    parser.add_argument("--dir", type=str, help="Директория с документами")
    parser.add_argument("--output", type=str, help="Директория для результатов")
    args = parser.parse_args()

    out_dir = args.output or ("output/baseline" if args.baseline else "output/exp_llama_relations")
    cmd = [sys.executable, "-m"]
    if args.baseline:
        cmd.append("baseline.main")
        cmd.extend(["--output", str(ROOT / out_dir)])
    else:
        cmd.append("experiments.exp_llama_relations.run")
        if args.output:
            cmd.extend(["--output", str(ROOT / args.output)])
    if args.file:
        cmd.extend(["--file", args.file])
    elif args.dir:
        cmd.extend(["--dir", args.dir])

    subprocess.run(cmd, cwd=str(ROOT), check=False)


if __name__ == "__main__":
    main()
