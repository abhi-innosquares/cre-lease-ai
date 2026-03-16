"""
Language detection and translation helpers.
"""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional

from src.config.settings import Settings
from src.utils.logger import get_logger


logger = get_logger(__name__)


def _contains_non_latin_script(text: str) -> bool:
    # Covers common non-Latin scripts seen in lease corpora.
    script_ranges = [
        r"[\u0400-\u04FF]",  # Cyrillic
        r"[\u0600-\u06FF]",  # Arabic
        r"[\u0900-\u097F]",  # Devanagari
        r"[\u4E00-\u9FFF]",  # CJK Unified Ideographs
        r"[\u3040-\u30FF]",  # Hiragana + Katakana
        r"[\uAC00-\uD7AF]",  # Hangul
    ]
    return any(re.search(pattern, text) for pattern in script_ranges)


def _chunk_text(text: str, max_chars: int = 10000) -> List[str]:
    if len(text) <= max_chars:
        return [text]

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for paragraph in text.split("\n\n"):
        para_len = len(paragraph) + 2
        if current and current_len + para_len > max_chars:
            chunks.append("\n\n".join(current))
            current = [paragraph]
            current_len = para_len
        else:
            current.append(paragraph)
            current_len += para_len

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def _get_openai_client():
    api_key = os.environ.get("OPENAI_API_KEY") or Settings.OPENAI_API_KEY
    if not api_key:
        return None

    try:
        import openai

        return openai.OpenAI(api_key=api_key)
    except Exception:
        return None


def detect_language_info(text: str) -> Dict[str, Optional[str]]:
    """
    Detect whether text is English. Uses OpenAI when available and
    falls back to script heuristics when it is not.
    """
    sample = (text or "").strip()
    if not sample:
        return {
            "language": "unknown",
            "is_english": True,
            "needs_translation": False,
            "source": "empty",
        }

    sample = sample[:4000]
    heuristic_non_latin = _contains_non_latin_script(sample)

    client = _get_openai_client()
    if not client:
        language = "non-english" if heuristic_non_latin else "english_or_unknown"
        return {
            "language": language,
            "is_english": not heuristic_non_latin,
            "needs_translation": heuristic_non_latin,
            "source": "heuristic",
        }

    prompt = (
        "Detect the primary language of the text and return JSON only with keys: "
        "language (string), is_english (boolean)."
    )

    try:
        response = client.chat.completions.create(
            model=Settings.OPENAI_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are a language detection assistant."},
                {"role": "user", "content": f"{prompt}\n\nText:\n{sample}"},
            ],
        )
        payload = json.loads(response.choices[0].message.content)
        language = str(payload.get("language") or "unknown")
        is_english = bool(payload.get("is_english"))
        return {
            "language": language,
            "is_english": is_english,
            "needs_translation": not is_english,
            "source": "openai",
        }
    except Exception as exc:
        logger.warning("Language detection via OpenAI failed, falling back to heuristic: %s", exc)
        language = "non-english" if heuristic_non_latin else "english_or_unknown"
        return {
            "language": language,
            "is_english": not heuristic_non_latin,
            "needs_translation": heuristic_non_latin,
            "source": "heuristic",
        }


def translate_to_english_if_needed(text: str) -> Dict[str, object]:
    """
    Translate non-English text to English when enabled.
    Returns translated text plus metadata.
    """
    language_info = detect_language_info(text)
    needs_translation = bool(language_info.get("needs_translation"))

    if not Settings.AUTO_TRANSLATE_TO_ENGLISH:
        return {
            "text": text,
            "translated": False,
            "language_info": language_info,
        }

    if not needs_translation:
        return {
            "text": text,
            "translated": False,
            "language_info": language_info,
        }

    client = _get_openai_client()
    if not client:
        logger.warning(
            "Detected non-English text, but OPENAI_API_KEY is not configured. "
            "Continuing without translation."
        )
        return {
            "text": text,
            "translated": False,
            "language_info": language_info,
        }

    chunks = _chunk_text(text, max_chars=10000)
    translated_chunks: List[str] = []

    translate_prompt = (
        "Translate the following lease text to clear professional English. "
        "Preserve legal meaning, numeric values, dates, currencies, and clause structure. "
        "Return only translated text without explanation."
    )

    for idx, chunk in enumerate(chunks, start=1):
        try:
            response = client.chat.completions.create(
                model=Settings.OPENAI_MODEL,
                temperature=0,
                messages=[
                    {"role": "system", "content": "You are a legal document translator."},
                    {
                        "role": "user",
                        "content": f"{translate_prompt}\n\nChunk {idx}/{len(chunks)}:\n{chunk}",
                    },
                ],
            )
            translated_chunks.append((response.choices[0].message.content or "").strip())
        except Exception as exc:
            logger.error("Translation failed on chunk %s/%s: %s", idx, len(chunks), exc)
            return {
                "text": text,
                "translated": False,
                "language_info": language_info,
                "error": str(exc),
            }

    return {
        "text": "\n\n".join(translated_chunks),
        "translated": True,
        "language_info": language_info,
    }
