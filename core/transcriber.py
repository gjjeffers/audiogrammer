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


def _clip_to_duration(segments: List[Segment], duration: float) -> List[Segment]:
    """Drop or trim segments/words that extend past the actual audio duration."""
    result = []
    for seg in segments:
        if seg.start >= duration:
            continue
        clipped_words = [w for w in seg.words if w.start < duration]
        for w in clipped_words:
            if w.end > duration:
                w.end = duration
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

    return _clip_to_duration(segments, duration)
