from __future__ import annotations

import re

TIMESTAMP = re.compile(r"(?:\[?\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d+)?\]?|-->)")
NUMBERING = re.compile(r"^\s*(?:\d+|\d+[.)]\s+.*)$")
SPEAKER_OR_METADATA = re.compile(r"^\s*[A-Za-z][A-Za-z0-9 _-]{0,39}:\s+\S")
COMMENT = re.compile(r"^\s*(?:#|//|;)\s*")


def validate_raw_lines(lines: list[tuple[int, str]]) -> None:
    if not lines:
        raise ValueError("Script must contain at least one non-empty line")
    errors: list[str] = []
    for number, text in lines:
        if TIMESTAMP.search(text):
            errors.append(f"line {number}: timestamps are not allowed")
        if NUMBERING.match(text):
            errors.append(f"line {number}: subtitle numbering is not allowed")
        if SPEAKER_OR_METADATA.match(text):
            errors.append(f"line {number}: speaker labels or metadata are not supported")
        if COMMENT.match(text):
            errors.append(f"line {number}: comments are not allowed")
        if "\x00" in text:
            errors.append(f"line {number}: NUL characters are not allowed")
    if errors:
        raise ValueError("Invalid script:\n" + "\n".join(errors))
