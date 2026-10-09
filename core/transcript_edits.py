import difflib
from typing import List, Optional, Tuple

from core.transcriber import Segment, Word


def fmt_time(seconds: float) -> str:
    """Format as M:SS.cc so headers keep enough precision to round-trip."""
    total_cs = max(0, int(round(seconds * 100)))
    m, rem = divmod(total_cs, 6000)
    s, cs = divmod(rem, 100)
    return f"{m}:{s:02d}.{cs:02d}"


def header(seg: Segment) -> str:
    return f"[{fmt_time(seg.start)} – {fmt_time(seg.end)}]"


def _parse_time(text: str) -> Optional[float]:
    """Parse [H:]M:SS[.fff] (or plain seconds) into seconds; None if invalid."""
    parts = text.strip().split(":")
    if not 1 <= len(parts) <= 3:
        return None
    try:
        values = [float(p) for p in parts]
    except ValueError:
        return None
    if any(v < 0 for v in values):
        return None
    secs = 0.0
    for v in values:
        secs = secs * 60 + v
    return secs


def _parseheader(line: str) -> Optional[Tuple[float, float]]:
    """Return (start, end) if line is a [start – end] header, else None."""
    stripped = line.strip()
    if not (stripped.startswith("[") and stripped.endswith("]")):
        return None
    for dash in ("–", "—", "-"):
        if dash in stripped:
            left, _, right = stripped[1:-1].partition(dash)
            start, end = _parse_time(left), _parse_time(right)
            if start is not None and end is not None:
                return start, end
    return None


def segments_to_text(segments: List[Segment]) -> str:
    lines = []
    for seg in segments:
        lines.append(header(seg))
        lines.append(seg.text)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _spread(texts: List[str], lo: float, hi: float) -> List[Word]:
    n = len(texts)
    return [
        Word(text=t, start=lo + i * (hi - lo) / n, end=lo + (i + 1) * (hi - lo) / n)
        for i, t in enumerate(texts)
    ]


def _retime_words(
    orig_words: List[Word], new_texts: List[str], start: float, end: float,
    orig_start: float, orig_end: float,
) -> List[Word]:
    """Words for edited text inside [start, end].

    Unchanged words keep their original timing (mapped onto the new span if the
    header was moved); inserted/replaced words are spread over the gap between
    their timed neighbours instead of re-spreading the whole segment.
    """
    if not orig_words:
        return _spread(new_texts, start, end) if new_texts else []

    span = orig_end - orig_start
    scale = (end - start) / span if span > 0 else 1.0

    def mp(t: float) -> float:
        if span <= 0:
            return start
        return start + (t - orig_start) * scale

    old_texts = [w.text for w in orig_words]
    if len(new_texts) == len(old_texts):
        return [
            Word(text=t, start=mp(o.start), end=mp(o.end))
            for t, o in zip(new_texts, orig_words)
        ]

    result: List[Word] = []
    matcher = difflib.SequenceMatcher(a=old_texts, b=new_texts, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for o, t in zip(orig_words[i1:i2], new_texts[j1:j2]):
                result.append(Word(text=t, start=mp(o.start), end=mp(o.end)))
        elif tag in ("replace", "insert"):
            lo = result[-1].end if result else start
            hi = mp(orig_words[i2].start) if i2 < len(orig_words) else end
            if tag == "replace":
                lo = max(lo, mp(orig_words[i1].start)) if result else mp(orig_words[i1].start)
                hi = mp(orig_words[i2 - 1].end)
            if hi <= lo:
                hi = min(end, lo + 0.1 * (j2 - j1))
            result.extend(_spread(new_texts[j1:j2], lo, hi))
        # "delete": nothing to emit
    return _separate_starts(result)


def _separate_starts(words: List[Word]) -> List[Word]:
    """Words that share a start time (an insert with no gap before its
    neighbour) would never be highlighted separately; share their span."""
    out: List[Word] = []
    i = 0
    while i < len(words):
        j = i + 1
        while j < len(words) and words[j].start - words[i].start < 1e-6:
            j += 1
        group = words[i:j]
        if len(group) > 1:
            hi = max(w.end for w in group)
            out.extend(_spread([w.text for w in group], group[0].start, hi))
        else:
            out.extend(group)
        i = j
    return out


def apply_edits(original: List[Segment], edited_text: str) -> List[Segment]:
    """Reconcile edited transcript text back into a segment list.

    Each block is introduced by a [M:SS.cc – M:SS.cc] header. The header times
    are authoritative: editing them moves the caption. Unchanged headers keep
    the original timing exactly. Within a block, unchanged words keep their
    word timing; added/changed words are timed within the surrounding gap.
    """
    blocks: List[Tuple[Optional[Tuple[float, float]], List[str]]] = []
    for line in edited_text.splitlines():
        parsed = _parseheader(line)
        if parsed is not None:
            blocks.append((parsed, []))
        elif blocks:
            blocks[-1][1].append(line)
        elif line.strip():
            blocks.append((None, [line]))

    # Pair each block with an original segment: by index when the block count
    # is unchanged, otherwise by matching (unchanged) header text.
    same_count = len(blocks) == len(original)
    by_header = {}
    for i, seg in enumerate(original):
        by_header.setdefault(header(seg), i)
    used = set()

    result: List[Segment] = []
    for i, (times, lines) in enumerate(blocks):
        edited_words = " ".join(lines).split()
        if same_count:
            oi = i
        elif times is not None:
            oi = by_header.get(f"[{fmt_time(times[0])} – {fmt_time(times[1])}]")
            if oi in used:
                oi = None
        else:
            oi = None
        orig = original[oi] if oi is not None else None
        if oi is not None:
            used.add(oi)

        if times is None:
            if orig is None:
                continue
            start, end = orig.start, orig.end
        else:
            start, end = times
            # Header unchanged at display precision -> keep exact original.
            if orig is not None and (
                fmt_time(start) == fmt_time(orig.start)
                and fmt_time(end) == fmt_time(orig.end)
            ):
                start, end = orig.start, orig.end
        if end < start:
            end = start

        if not edited_words:
            if orig is not None and (start, end) == (orig.start, orig.end):
                result.append(orig)
            continue

        if orig is not None:
            words = _retime_words(
                orig.words, edited_words, start, end, orig.start, orig.end
            )
        else:
            words = _spread(edited_words, start, end)

        result.append(Segment(
            text=" ".join(edited_words), start=start, end=end, words=words,
        ))

    result.sort(key=lambda sg: sg.start)
    return result
