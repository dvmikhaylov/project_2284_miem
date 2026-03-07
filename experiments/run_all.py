"""
Запуск двух подходов: baseline и OpenRouter.
Результаты: output/baseline/ и output/exp_llama_relations/
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    # 1) Baseline: NER (Natasha), связи по паттернам, классификация по ключевым словам
    print("\n" + "=" * 60)
    print("1. Baseline")
    print("=" * 60)
    r1 = subprocess.run(
        [sys.executable, "-m", "baseline.main", "--dir", str(ROOT / "validate_data"), "--output", str(ROOT / "output" / "baseline")],
        cwd=str(ROOT),
        capture_output=False,
    )
    if r1.returncode != 0:
        print("  [!] Baseline завершился с кодом", r1.returncode)

    # 2) OpenRouter: один вызов LLM на документ (NER + связи + бизнес-процесс)
    print("\n" + "=" * 60)
    print("2. OpenRouter (LLM)")
    print("=" * 60)
    r2 = subprocess.run(
        [sys.executable, "-m", "experiments.exp_llama_relations.run"],
        cwd=str(ROOT),
        capture_output=False,
    )
    if r2.returncode != 0:
        print("  [!] OpenRouter завершился с кодом", r2.returncode)

    print("\n" + "=" * 60)
    print("Готово. Результаты: output/baseline/ и output/exp_llama_relations/")


if __name__ == "__main__":
    main()
