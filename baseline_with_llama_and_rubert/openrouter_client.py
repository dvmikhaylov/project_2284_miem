"""
Вызов бесплатной модели OpenRouter (gpt-oss-120b:free) для NER и извлечения связей.
API: https://openrouter.ai/docs — OpenAI-совместимый chat/completions.

Нужен ключ: https://openrouter.ai/keys → задать env OPENROUTER_API_KEY.
Ретраи при 429 (rate limit): OPENROUTER_RETRIES, OPENROUTER_RETRY_DELAY, timeout — см. параметры.
"""
import json
import time
import urllib.request
import urllib.error
from typing import Optional

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Настройки из env (опционально)
import os as _os
_default_retries = int(_os.environ.get("OPENROUTER_RETRIES", "1"))
_default_delay = float(_os.environ.get("OPENROUTER_RETRY_DELAY", "10"))
_default_timeout = int(_os.environ.get("OPENROUTER_TIMEOUT", "300"))


def call_openrouter(
    prompt: str,
    *,
    api_key: str,
    model: str = "openai/gpt-4o",
    max_tokens: int = 800,
    temperature: float = 0.0,
    timeout: int = None,
    max_retries: int = None,
    retry_delay: float = None,
) -> Optional[str]:
    """
    Отправляет промпт в OpenRouter, возвращает content ответа или None при ошибке.
    При 429 (rate limit) повторяет запрос до max_retries раз с паузой retry_delay сек.
    """
    timeout = timeout if timeout is not None else _default_timeout
    max_retries = max_retries if max_retries is not None else _default_retries
    retry_delay = retry_delay if retry_delay is not None else _default_delay

    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    data = json.dumps(body).encode("utf-8")
    last_error = None
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(
            OPENROUTER_URL,
            data=data,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                out = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body_read = e.read().decode("utf-8", errors="replace") if e.fp else ""
            if e.code == 429 and attempt < max_retries:
                wait = retry_delay * (attempt + 1)
                if _os.environ.get("DEBUG_OPENROUTER"):
                    print(f"[OpenRouter] 429 rate limit, повтор через {wait:.0f} с (попытка {attempt + 1}/{max_retries + 1})")
                time.sleep(wait)
                last_error = None
                continue
            if e.code == 429:
                return None
            raise RuntimeError(f"OpenRouter HTTP {e.code}: {body_read[:500]}") from e
        except (TimeoutError, OSError, urllib.error.URLError) as e:
            last_error = e
            if attempt < max_retries:
                wait = retry_delay * (attempt + 1)
                if _os.environ.get("DEBUG_OPENROUTER"):
                    print(f"[OpenRouter] Таймаут/сеть, повтор через {wait:.0f} с (попытка {attempt + 1}/{max_retries + 1})")
                time.sleep(wait)
                continue
            raise RuntimeError(f"OpenRouter request failed: {e}") from e
        except Exception as e:
            raise RuntimeError(f"OpenRouter request failed: {e}") from e

        err = out.get("error")
        if err:
            raise RuntimeError(f"OpenRouter API error: {err}")
        try:
            content = (out.get("choices") or [{}])[0].get("message", {}) or {}
            text = content.get("content") if content else None
            result = (text or "").strip() or None
            if result is None and attempt < max_retries:
                # Пустой content — иногда помогает повтор
                if _os.environ.get("DEBUG_OPENROUTER"):
                    print(f"[OpenRouter] Пустой content, повтор через {retry_delay:.0f} с (попытка {attempt + 1}/{max_retries + 1})")
                time.sleep(retry_delay * (attempt + 1))
                continue
            return result
        except (IndexError, KeyError, TypeError):
            return None
    return None
