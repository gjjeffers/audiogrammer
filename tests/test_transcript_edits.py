import pytest

from core.transcriber import Segment, Word
from core.transcript_edits import apply_edits as _apply_edits, segments_to_text as _segments_to_text


def _seg(start, end, words):
    n = len(words)
    d = (end - start) / n
    ws = [Word(t, start + i * d, start + (i + 1) * d) for i, t in enumerate(words)]
    return Segment(" ".join(words), start, end, ws)


@pytest.fixture
def segs():
    return [_seg(1.234, 3.0, ["hello", "big", "world"]), _seg(61.5, 63.5, ["bye", "now"])]


def test_roundtrip_preserves_exact_timing(segs):
    out = _apply_edits(segs, _segments_to_text(segs))
    assert [(s.start, s.end) for s in out] == [(1.234, 3.0), (61.5, 63.5)]
    assert [(w.start, w.end) for w in out[0].words] == [(w.start, w.end) for w in segs[0].words]


def test_edited_header_moves_caption(segs):
    text = _segments_to_text(segs).replace("[0:01.23", "[0:05.00", 1)
    out = _apply_edits(segs, text)
    assert out[0].start == pytest.approx(5.0)
    assert out[0].words[0].start == pytest.approx(5.0)
    assert out[0].end == 3.0 or out[0].end >= out[0].start


def test_shifted_header_shifts_words(segs):
    text = _segments_to_text(segs).replace("[0:01.23 – 0:03.00]", "[0:11.23 – 0:13.00]")
    out = _apply_edits(segs, text)
    assert out[0].words[0].start == pytest.approx(11.234, abs=0.01)
    assert out[0].words[-1].end == pytest.approx(13.0, abs=0.01)


def test_added_word_keeps_other_word_timing(segs):
    text = _segments_to_text(segs).replace("hello big world", "hello very big world")
    out = _apply_edits(segs, text)
    w = out[0].words
    assert [x.text for x in w] == ["hello", "very", "big", "world"]
    assert w[0].start == segs[0].words[0].start
    assert w[3].end == segs[0].words[2].end
    assert w[0].start < w[1].start < w[2].start < w[3].start


def test_unparseable_header_text_is_not_dropped(segs):
    out = _apply_edits(segs, "[0:01.23 – 0:03.00]\nhello there world\n")
    assert out[0].text == "hello there world"
