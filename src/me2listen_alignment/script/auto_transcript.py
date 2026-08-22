from __future__ import annotations

import re

from ..models import ScriptLine
from .normalizer import normalize_alignment_text, tokenize


_SENTENCE_BREAK = re.compile(r"(?<=[.!?])(?:\s+|$)")
# \b keeps the ordinal suffix of "1st." / "21st." from reading as "St.".
_TRAILING_WORD = re.compile(r"\b([A-Za-z]+)\.$")
MIN_SENTENCE_WORDS = 5

# Words whose trailing period is an abbreviation mark, never a sentence end.
# Kept deliberately small: a wrong join merges two cues, which is milder than a
# cue starting mid-sentence, but that asymmetry only justifies entries that
# essentially never end an English sentence. Words that genuinely do end one
# ("etc.", "Inc.", "Jr.") stay out, as do military/political titles absent from
# this lesson material, since each entry only adds false-positive surface.
ABBREVIATIONS = frozenset({"mr", "mrs", "ms", "dr", "prof", "rev", "st"})


def _abbreviation_before_break(piece: str) -> bool:
    """True when this piece ends mid-sentence rather than at a real full stop.

    Single letters are NOT treated as initials: protecting "J. K. Rowling"
    would cost every sentence ending in "I." or a spoken letter ("The answer
    is A."), which this lesson material is far more likely to contain.
    """
    match = _TRAILING_WORD.search(piece)
    if not match:
        return False
    word = match.group(1)
    # Capitalization separates the title "Ms." from the unit "500 ms.".
    return word[:1].isupper() and word.casefold() in ABBREVIATIONS


def split_english_sentences(text: str) -> list[str]:
    """Split only at punctuation produced by the transcription model.

    Wordless fragments (punctuation the model emits for noise or hesitation)
    are dropped here, before abbreviation joining, so their text can never ride
    into a sentence on the back of a preceding abbreviation.
    """
    sentences: list[str] = []
    for raw in _SENTENCE_BREAK.split(text.strip()):
        piece = raw.strip()
        if not piece or not tokenize(piece):
            continue
        if sentences and _abbreviation_before_break(sentences[-1]):
            sentences[-1] = f"{sentences[-1]} {piece}"
        else:
            sentences.append(piece)
    return sentences


def _merge_short_sentences(sentences: list[str], min_words: int) -> list[str]:
    """Fold a sentence under `min_words` words into the sentence after it."""
    merged: list[str] = []
    carry = ""
    for sentence in sentences:
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
