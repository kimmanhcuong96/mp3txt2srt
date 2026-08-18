from __future__ import annotations

from pathlib import Path

from ..models import ScriptLine
from .normalizer import normalize_alignment_text, tokenize
from .validator import validate_raw_lines


def parse_script(path: Path) -> list[ScriptLine]:
    if not path.is_file():
        raise FileNotFoundError(f"Script file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Script must be valid UTF-8: {path}") from exc
    raw_lines = [(number, line) for number, line in enumerate(text.splitlines(), 1) if line.strip()]
    validate_raw_lines(raw_lines)
    parsed: list[ScriptLine] = []
    for index, (source_number, original) in enumerate(raw_lines, 1):
        alignment_text = normalize_alignment_text(original)
        tokens = tokenize(alignment_text)
        if not tokens:
            raise ValueError(f"Script line {source_number} contains no alignable words")
        parsed.append(ScriptLine(index, source_number, original, alignment_text, tokens))
    return parsed

