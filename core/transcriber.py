from dataclasses import dataclass, field
from typing import List, Optional, Callable


@dataclass
class Word:
    text: str
    start: float
    end: float


@dataclass
class Segment:
    text: str
    start: float
    end: float
    words: List[Word] = field(default_factory=list)


# Silence between two words at least this long (seconds) starts a new caption
# segment. Whisper only breaks segments on long pauses, which makes captions
# chunky; this splits on much shorter ones.
PAUSE_THRESHOLD = 0.3

# Pauses are measured at this resolution (a tenth of a second) so float noise
# in Whisper's timestamps can't push a 0.3s gap just under the threshold.
_TIME_RESOLUTION = 0.1


def _gap_tenths(prev_end: float, next_start: float) -> int:
    """Silence between two words, in whole tenths of a second."""
    return int(round((next_start - prev_end) / _TIME_RESOLUTION))


def _split_on_pauses(segments: List[Segment], pause_threshold: float) -> List[Segment]:
    """Split each segment wherever consecutive words are separated by a pause
    of at least pause_threshold seconds."""
    min_gap = int(round(pause_threshold / _TIME_RESOLUTION))
    result: List[Segment] = []
    for seg in segments:
        words = seg.words
        if len(words) < 2:
            result.append(seg)
            continue

        groups: List[List[Word]] = [[words[0]]]
        for prev, word in zip(words, words[1:]):
            if _gap_tenths(prev.end, word.start) >= min_gap:
                groups.append([word])
            else:
                groups[-1].append(word)

        if len(groups) == 1:
            result.append(seg)
            continue

        for i, group in enumerate(groups):
            # Keep the original segment bounds at the outer edges so nothing
            # Whisper reported is lost; inner edges follow the words.
            result.append(Segment(
                text=" ".join(w.text for w in group if w.text),
                start=seg.start if i == 0 else group[0].start,
                end=seg.end if i == len(groups) - 1 else group[-1].end,
                words=group,
            ))
    return result


def _clip_to_duration(segments: List[Segment], duration: float) -> List[Segment]:
    """Drop or trim segments/words that extend past the actual audio duration."""
    result = []
    for seg in segments:
        if seg.start >= duration:
            continue
        if seg.end <= seg.start:
            continue
        clipped_words = [w for w in seg.words if w.start < duration]
        for w in clipped_words:
            if w.end > duration:
                w.end = duration
        if not seg.text.strip() and not clipped_words:
            continue
        result.append(Segment(
            text=seg.text,
            start=seg.start,
            end=min(seg.end, duration),
            words=clipped_words,
        ))
    return result


def transcribe(
    audio_path: str,
    model_size: str = "base",
    status_callback: Optional[Callable[[str], None]] = None,
    trim_start: Optional[float] = None,
    trim_end: Optional[float] = None,
    pause_threshold: float = PAUSE_THRESHOLD,
) -> List[Segment]:
    import whisper

    from core.trim import should_trim, slice_audio

    if status_callback:
        status_callback(f"Loading Whisper model '{model_size}'...")

    model = whisper.load_model(model_size)

    if status_callback:
        status_callback("Transcribing audio (this may take a moment)...")

    sr = whisper.audio.SAMPLE_RATE
    samples = whisper.load_audio(audio_path)
    if should_trim(trim_start, trim_end):
        samples = slice_audio(samples, sr, trim_start, trim_end)
    result = model.transcribe(samples, word_timestamps=True)
    duration = len(samples) / sr

    segments: List[Segment] = []
    for seg_data in result["segments"]:
        words: List[Word] = []
        for w in seg_data.get("words", []):
            words.append(Word(
                text=w["word"].strip(),
                start=float(w["start"]),
                end=float(w["end"]),
            ))

        # Fall back to segment-level timing if no word timestamps
        if not words and seg_data.get("text", "").strip():
            for token in seg_data["text"].strip().split():
                words.append(Word(
                    text=token,
                    start=float(seg_data["start"]),
                    end=float(seg_data["end"]),
                ))

        segments.append(Segment(
            text=seg_data["text"].strip(),
            start=float(seg_data["start"]),
            end=float(seg_data["end"]),
            words=words,
        ))

    segments = _split_on_pauses(segments, pause_threshold)
    return _clip_to_duration(segments, duration)
