from core.transcriber import Segment, Word, _clip_to_duration, _split_on_pauses


def _seg(*words):
    ws = [Word(t, s, e) for t, s, e in words]
    return Segment(" ".join(w.text for w in ws), ws[0].start, ws[-1].end, ws)


def test_splits_on_short_pause():
    seg = _seg(("hello", 0.0, 0.4), ("world", 0.8, 1.2), ("again", 1.3, 1.6))
    out = _split_on_pauses([seg], 0.3)
    assert [s.text for s in out] == ["hello", "world again"]
    assert out[0].start == 0.0 and out[0].end == 0.4
    assert out[1].start == 0.8 and out[1].end == 1.6


def test_gap_below_threshold_is_not_split():
    seg = _seg(("a", 0.0, 0.5), ("b", 0.7, 1.0))  # 0.2s gap
    assert len(_split_on_pauses([seg], 0.3)) == 1


def test_gap_exactly_at_threshold_splits_despite_float_noise():
    # 0.8 - 0.5 is 0.30000000000000004 / 0.2999... depending on values
    seg = _seg(("a", 0.0, 0.5), ("b", 0.8, 1.0))
    assert len(_split_on_pauses([seg], 0.3)) == 2


def test_outer_segment_bounds_preserved():
    seg = Segment("a b", 0.0, 3.0, [Word("a", 0.5, 0.9), Word("b", 2.0, 2.4)])
    out = _split_on_pauses([seg], 0.3)
    assert out[0].start == 0.0 and out[0].end == 0.9
    assert out[1].start == 2.0 and out[1].end == 3.0


def test_clip_keeps_subsecond_segments():
    seg = _seg(("hi", 1.1, 1.4))
    assert len(_clip_to_duration([seg], 10.0)) == 1
