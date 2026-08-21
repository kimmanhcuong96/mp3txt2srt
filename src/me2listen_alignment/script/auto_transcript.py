from __future__ import annotations

import re

from ..models import ScriptLine
from .normalizer import normalize_alignment_text, tokenize


_SENTENCE_BREAK = re.compile(r"(?<=[.!?])(?:\s+|$)")


def split_english_sentences(text: str) -> list[str]:
    """Split only at punctuation produced by the transcription model."""
    sentences = [piece.strip() for piece in _SENTENCE_BREAK.split(text.strip()) if piece.strip()]
    return sentences


def transcript_to_script_lines(text: str) -> list[ScriptLine]:
    lines: list[ScriptLine] = []
    for index, sentence in enumerate(split_english_sentences(text), 1):
        alignment_text = normalize_alignment_text(sentence)
        tokens = tokenize(alignment_text)
        if tokens:
            lines.append(ScriptLine(index, index, sentence, alignment_text, tokens))
    if not lines:
        raise ValueError("Transcription contains no alignable English sentences")
    return lines
