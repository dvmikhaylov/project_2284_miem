"""
Скачивает GGUF-модель для llama.cpp (связи или NER).
  python scripts/download_llama_model.py              # 0.5B для связей
  python scripts/download_llama_model.py --for-ner    # 14B для NER
  python scripts/download_llama_model.py --for-ner-32b # 32B для NER (~19 ГБ)
"""
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"
HF_REPO_05 = "Qwen/Qwen2.5-0.5B-Instruct-GGUF"
DEFAULT_FILE = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
HF_REPO_14 = "Qwen/Qwen2.5-14B-Instruct-GGUF"
NER_FILE_14 = "qwen2.5-14b-instruct-q4_k_m.gguf"
BARTOWSKI_14 = ("bartowski/Qwen2.5-14B-Instruct-GGUF", "Qwen2.5-14B-Instruct-Q4_K_M.gguf")
NER_FILE_32 = "qwen2.5-32b-instruct-q4_k_m.gguf"
BARTOWSKI_32 = ("bartowski/Qwen2.5-32B-Instruct-GGUF", "Qwen2.5-32B-Instruct-Q4_K_M.gguf")


def main():
    parser = argparse.ArgumentParser(description="Скачать GGUF модель для llama.cpp")
    parser.add_argument("--model", type=str, default=None, help="Имя файла (по умолчанию — из --for-ner)")
    parser.add_argument("--dir", type=str, default=None, help=f"Папка для модели (по умолчанию {MODELS_DIR})")
    parser.add_argument("--for-ner", action="store_true", help="Скачать Qwen2.5-14B для NER")
    parser.add_argument("--for-ner-32b", action="store_true", help="Скачать Qwen2.5-32B для NER (~19 ГБ)")
    args = parser.parse_args()

    out_dir = Path(args.dir) if args.dir else MODELS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.for_ner_32b:
        repo, filename = None, None
        dest = out_dir / NER_FILE_32
        alt_sources = [BARTOWSKI_32]
        dest_alt = out_dir / BARTOWSKI_32[1]
    elif args.for_ner:
        repo, filename = HF_REPO_14, NER_FILE_14
        dest = out_dir / NER_FILE_14
        alt_sources = [(HF_REPO_14, NER_FILE_14), BARTOWSKI_14]
        dest_alt = out_dir / BARTOWSKI_14[1]
    else:
        repo, filename = HF_REPO_05, args.model or DEFAULT_FILE
        dest = out_dir / filename
        alt_sources = [(repo, filename), ("QuantFactory/Qwen2.5-0.5B-GGUF", "Qwen2.5-0.5B.Q4_K_M.gguf")]
        dest_alt = None

    if dest.exists() or (dest_alt and dest_alt.exists()):
        print(f"Модель уже есть: {dest}")
        if args.for_ner or args.for_ner_32b:
            print("Конфиг подхватит её как NER_LLAMA_MODEL_PATH.")
        return

    def download_via_urllib(repo_name: str, fname: str):
        save_to = dest if (args.for_ner or args.for_ner_32b) else out_dir / fname
        url = f"https://huggingface.co/{repo_name}/resolve/main/{fname}"
        print(f"Скачиваю {url} в {save_to}...")
        import urllib.request
        urllib.request.urlretrieve(url, save_to)
        return str(save_to)

    if args.for_ner_32b:
        # 32B: сначала huggingface_hub (часто стабильнее по сети), потом urllib
        print("Скачиваю 32B для NER...")
        path = None
        try:
            from huggingface_hub import hf_hub_download
            repo_name, fname = BARTOWSKI_32
            path = hf_hub_download(repo_id=repo_name, filename=fname, local_dir=str(out_dir), local_dir_use_symlinks=False)
            if path and Path(path).name != NER_FILE_32:
                (out_dir / Path(path).name).rename(out_dir / NER_FILE_32)
                path = str(out_dir / NER_FILE_32)
        except Exception as e:
            print(f"  hf_hub: {e}")
        if not path or not Path(path).exists():
            for repo_name, fname in alt_sources:
                try:
                    path = download_via_urllib(repo_name, fname)
                    break
                except Exception as e:
                    print(f"  {repo_name}: {e}")
        if path and Path(path).exists():
            print(f"Готово: {path}")
            print("Конфиг подхватит как NER_LLAMA_MODEL_PATH.")
        else:
            print("Не удалось скачать (проверьте интернет/DNS/VPN).")
            print("Ручная загрузка: откройте в браузере")
            print("  https://huggingface.co/bartowski/Qwen2.5-32B-Instruct-GGUF/tree/main")
            print("  скачайте Qwen2.5-32B-Instruct-Q4_K_M.gguf и положите в папку models/")
            print(f"  как файл: {NER_FILE_32}")
        return

    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("huggingface_hub не установлен, пробую прямую загрузку (urllib)...")
        for repo_name, fname in alt_sources:
            try:
                path = download_via_urllib(repo_name, fname)
                print(f"Готово: {path}")
                return
            except Exception as e:
                print(f"  {repo_name}: {e}")
        print("Установите: pip install huggingface_hub")
        return

    print(f"Скачиваю {filename} из {repo} в {out_dir}...")
    path = None
    try:
        path = hf_hub_download(repo_id=repo, filename=filename, local_dir=str(out_dir), local_dir_use_symlinks=False)
    except Exception as e:
        print(f"hf_hub ошибка: {e}, пробую прямую загрузку...")
        for repo_name, fname in alt_sources:
            try:
                path = download_via_urllib(repo_name, fname)
                break
            except Exception as e2:
                print(f"  {repo_name}: {e2}")
    if path:
        print(f"Готово: {path}")
        print("Конфиг подхватит модель автоматически." + (" (NER_LLAMA_MODEL_PATH)" if args.for_ner else " (LLAMA_MODEL_PATH)"))
    else:
        print("Не удалось скачать.")


if __name__ == "__main__":
    main()
