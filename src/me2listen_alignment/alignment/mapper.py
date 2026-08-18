from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from ..models import AlignedWord, ScriptLine, SubtitleCue


@dataclass(frozen=True, slots=True)
class MappingResult:
    cues: tuple[SubtitleCue, ...]
    expected_words: int
    matched_words: int
    unmatched_expected: tuple[str, ...]

    @property
    def coverage(self) -> float:
        return self.matched_words / self.expected_words if self.expected_words else 0.0


def map_words_to_lines(lines: list[ScriptLine], aligned_words: tuple[AlignedWord, ...]) -> MappingResult:
    expected: list[str] = []
    owners: list[int] = []
    for line_position, line in enumerate(lines):
        expected.extend(line.tokens)
        owners.extend([line_position] * len(line.tokens))
    actual = [word.normalized for word in aligned_words]
    matcher = SequenceMatcher(a=expected, b=actual, autojunk=False)
    matches: dict[int, AlignedWord] = {}
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):
            matches[block.a + offset] = aligned_words[block.b + offset]

    cues: list[SubtitleCue] = []
    for line_position, line in enumerate(lines):
        positions = [position for position, owner in enumerate(owners) if owner == line_position]
        timed = [matches[position] for position in positions if position in matches]
        if not timed:
            continue
        scores = [word.score for word in timed if word.score is not None]
        cues.append(
            SubtitleCue(
                index=line.index,
                start=min(word.start for word in timed),
                end=max(word.end for word in timed),
                text=line.original,
                matched_words=len(timed),
                expected_words=len(line.tokens),
                average_score=sum(scores) / len(scores) if scores else None,
            )
        )
    unmatched = tuple(expected[index] for index in range(len(expected)) if index not in matches)
    return MappingResult(tuple(cues), len(expected), len(matches), unmatched)

