from __future__ import annotations

from dataclasses import replace

from ..models import AlignedWord, SubtitleCue


def refine_cue_boundaries(
    cues: tuple[SubtitleCue, ...],
    silence_intervals: tuple[tuple[float, float], ...],
    audio_duration: float,
    search_radius: float,
    speech_padding: float,
    words_by_line: tuple[tuple[AlignedWord, ...], ...] = (),
    embedded_silence_minimum: float = 0.30,
) -> tuple[SubtitleCue, ...]:
    """Snap cue edges to measured silence without inventing speech timestamps."""
    if not cues or not silence_intervals:
        return cues
    refined = list(cues)

    if words_by_line and words_by_line[0]:
        first_word = words_by_line[0][0]
        embedded = _embedded_silences(first_word, silence_intervals, embedded_silence_minimum)
    else:
        embedded = []
    if embedded:
        _, silence_end = max(embedded, key=lambda item: item[1] - item[0])
        new_start = max(0.0, silence_end - speech_padding)
        if new_start < refined[0].end:
            refined[0] = replace(refined[0], start=new_start)

    for index in range(len(refined) - 1):
        previous = refined[index]
        following = refined[index + 1]
        boundary = (previous.end + following.start) / 2.0
        candidates = []
        for silence_start, silence_end in silence_intervals:
            if silence_start <= previous.start or silence_end >= following.end:
                continue
            distance = _distance_to_interval(boundary, silence_start, silence_end)
            if distance <= search_radius:
                candidates.append((distance, abs((silence_start + silence_end) / 2 - boundary), silence_start, silence_end))
        if not candidates:
            continue
        _, _, silence_start, silence_end = min(candidates)
        new_end = silence_start + speech_padding
        new_start = silence_end - speech_padding
        if new_end >= new_start:
            midpoint = (silence_start + silence_end) / 2
            new_end = midpoint
            new_start = midpoint
        if previous.start < new_end <= new_start < following.end:
            refined[index] = replace(previous, end=new_end)
            refined[index + 1] = replace(following, start=new_start)

    if words_by_line and words_by_line[-1]:
        last_word = words_by_line[-1][-1]
        embedded = _embedded_silences(last_word, silence_intervals, embedded_silence_minimum)
    else:
        embedded = []
    if embedded:
        silence_start, _ = max(embedded, key=lambda item: item[1] - item[0])
        new_end = min(audio_duration, silence_start + speech_padding)
        if refined[-1].start < new_end:
            refined[-1] = replace(refined[-1], end=new_end)

    trailing = [
        interval for interval in silence_intervals
        if interval[1] >= audio_duration - 0.05
        and abs(interval[0] - refined[-1].end) <= search_radius
    ]
    if trailing:
        silence_start, _ = min(trailing, key=lambda item: abs(item[0] - refined[-1].end))
        new_end = min(audio_duration, silence_start + speech_padding)
        if refined[-1].start < new_end:
            refined[-1] = replace(refined[-1], end=new_end)
    return tuple(refined)


def _distance_to_interval(value: float, start: float, end: float) -> float:
    if start <= value <= end:
        return 0.0
    return min(abs(value - start), abs(value - end))


def _embedded_silences(
    word: AlignedWord,
    silence_intervals: tuple[tuple[float, float], ...],
    minimum_duration: float,
) -> list[tuple[float, float]]:
    embedded: list[tuple[float, float]] = []
    for silence_start, silence_end in silence_intervals:
        overlap_start = max(word.start, silence_start)
        overlap_end = min(word.end, silence_end)
        if overlap_end - overlap_start >= minimum_duration:
            embedded.append((silence_start, silence_end))
    return embedded
