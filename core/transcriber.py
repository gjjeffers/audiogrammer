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


def transcribe(
    audio_path: str,
    model_size: str = "base",
    status_callback: Optional[Callable[[str], None]] = None,
) -> List[Segment]:
    import whisper

    if status_callback:
        status_callback(f"Loading Whisper model '{model_size}'...")

    model = whisper.load_model(model_size)

    if status_callback:
        status_callback("Transcribing audio (this may take a moment)...")

    result = model.transcribe(audio_path, word_timestamps=True)

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

    return segments
