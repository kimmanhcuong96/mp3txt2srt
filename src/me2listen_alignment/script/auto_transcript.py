from __future__ import annotations

import re

from ..models import ScriptLine
from .normalizer import normalize_alignment_text, tokenize


_SENTENCE_BREAK = re.compile(r"(?<=[.!?])(?:\s+|$)")
MIN_SENTENCE_WORDS = 5


def split_english_sentences(text: str) -> list[str]:
    """Split only at punctuation produced by the transcription model."""
    sentences = [piece.strip() for piece in _SENTENCE_BREAK.split(text.strip()) if piece.strip()]
    return sentences


def _merge_short_sentences(sentences: list[str], min_words: int) -> list[str]:
    """Fold a sentence under `min_words` words into the sentence after it.

    Wordless fragments (punctuation the model emits for noise or hesitation)
    are discarded before merging, so their text can never ride into a cue on
    the back of the sentence they would otherwise merge into.
    """
    merged: list[str] = []
    carry = ""
    for sentence in sentences:
        if not tokenize(sentence):
            continue
        candidate = f"{carry} {sentence}".strip() if carry else sentence
        if len(tokenize(candidate)) < min_words:
            carry = candidate
        else:
            merged.append(candidate)
            carry = ""
    if carry:
        if merged:
            merged[-1] = f"{merged[-1]} {carry}".strip()
        else:
            merged.append(carry)
    return merged


def transcript_to_script_lines(
    text: str, min_sentence_words: int = MIN_SENTENCE_WORDS
) -> list[ScriptLine]:
    sentences = _merge_short_sentences(split_english_sentences(text), min_sentence_words)
    lines: list[ScriptLine] = []
    for index, sentence in enumerate(sentences, 1):
        alignment_text = normalize_alignment_text(sentence)
        lines.append(ScriptLine(index, index, sentence, alignment_text, tokenize(alignment_text)))
    if not lines:
        raise ValueError("Transcription contains no alignable English sentences")
    return lines
