from __future__ import annotations

import re
import unicodedata

APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "`": "'", "´": "'"})
QUOTES_DASHES = str.maketrans({"“": '"', "”": '"', "–": "-", "—": "-", "…": "..."})
TOKEN_RE = re.compile(r"[^\W_]+(?:['-][^\W_]+)*", re.UNICODE)


def normalize_alignment_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).translate(APOSTROPHES).translate(QUOTES_DASHES)
    return " ".join(value.split())


def tokenize(text: str) -> tuple[str, ...]:
    normalized = normalize_alignment_text(text).casefold()
    return tuple(match.group(0).strip("-'") for match in TOKEN_RE.finditer(normalized) if match.group(0).strip("-'"))

