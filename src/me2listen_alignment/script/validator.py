from __future__ import annotations

import re

BRACKETED_TIMESTAMP = re.compile(
    r"\[\s*\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d+)?\s*\]"
)
BARE_TIMESTAMP_LINE = re.compile(
    r"^\s*\d{1,2}:\d{2}:\d{2}(?:[.,]\d+)?\s*$"
)
NUMBERING = re.compile(r"^\s*(?:\d+|\d+[.)]\s+.*)$")
SPEAKER_OR_METADATA = re.compile(r"^\s*[A-Za-z][A-Za-z0-9 _-]{0,39}:\s+\S")
COMMENT = re.compile(r"^\s*(?:#|//|;)\s*")


def validate_raw_lines(lines: list[tuple[int, str]]) -> None:
    if not lines:
        raise ValueError("Script must contain at least one non-empty line")
    errors: list[str] = []
    for number, text in lines:
        # A clock time can be legitimate spoken text (for example,
        # "At 10:15 A.M. the students have recess."). Reject only explicit
        # subtitle timing syntax, not every occurrence of HH:MM.
        if (
            BRACKETED_TIMESTAMP.search(text)
            or "-->" in text
            or BARE_TIMESTAMP_LINE.fullmatch(text)
        ):
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
