"""
backend/processing/preprocessor.py
─────────────────────────────────────────────────────────────
Stage 2: Text cleaning and normalisation.
─────────────────────────────────────────────────────────────
"""

from __future__ import annotations
import re
import unicodedata
import logging
from typing import List

logger = logging.getLogger(__name__)


# ── Regex patterns ───────────────────────────────────────────

_CTRL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_PAGE_NUMBER_LINE = re.compile(
    r"^\s*(?:page\s+)?\d+(?:\s+of\s+\d+)?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_URL_LINE = re.compile(r"^\s*https?://\S+\s*$", re.MULTILINE)
_HORIZONTAL_RULE = re.compile(r"^[\s\-=_*#]{5,}\s*$", re.MULTILINE)
_EXCESS_NEWLINES = re.compile(r"\n{3,}")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")
_TRAILING_SPACE = re.compile(r"[ \t]+$", re.MULTILINE)


# ── Core cleaning function ────────────────────────────────────

def preprocess_text(text: str) -> str:
    """Clean and normalise extracted document text."""
    if not text or not text.strip():
        return ""

    original_len = len(text)

    text = unicodedata.normalize("NFC", text)
    text = _CTRL_CHARS.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _PAGE_NUMBER_LINE.sub("", text)
    text = _URL_LINE.sub("", text)
    text = _HORIZONTAL_RULE.sub("", text)
    text = _TRAILING_SPACE.sub("", text)
    text = _MULTI_SPACE.sub(" ", text)
    text = _EXCESS_NEWLINES.sub("\n\n", text)
    text = _deduplicate_lines(text)
    text = text.strip()

    cleaned_len = len(text)
    reduction_pct = (1 - cleaned_len / original_len) * 100 if original_len > 0 else 0
    logger.debug(
        "Preprocessed: %d → %d chars (%.1f%% reduction)",
        original_len, cleaned_len, reduction_pct,
    )

    return text


def _deduplicate_lines(text: str) -> str:
    """Remove consecutive duplicate lines."""
    lines = text.split("\n")
    deduped: List[str] = []
    prev = None

    for line in lines:
        stripped = line.strip()
        if stripped == "":
            deduped.append(line)
            prev = None
        elif stripped != prev:
            deduped.append(line)
            prev = stripped

    return "\n".join(deduped)


def get_text_stats(text: str) -> dict:
    """Returns basic statistics about the cleaned text."""
    lines = text.split("\n")
    words = text.split()
    paragraphs = [p for p in text.split("\n\n") if p.strip()]

    return {
        "char_count": len(text),
        "word_count": len(words),
        "line_count": len(lines),
        "paragraph_count": len(paragraphs),
        "avg_words_per_paragraph": len(words) / max(len(paragraphs), 1),
    }
