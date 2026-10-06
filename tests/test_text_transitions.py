from PIL import Image

from core.renderer import _visible_window, render_frame
from core.transcriber import Segment, Word
from core.transitions import TRANSITION_STYLES, TextTransition, composite_caption, transition_state


def _seg(start, end, text="hi"):
    return Segment(text, start, end, [Word(text, start, end)])


def test_transition_styles_map_to_ids():
    assert TRANSITION_STYLES == {"None": "none", "Fade": "fade", "Slide": "slide", "Zoom": "zoom"}


def test_no_transition_is_fully_visible():
    assert transition_state(None, 0.0, 2.0, 0.0) == ("none", 1.0)
    assert transition_state(TextTransition(), 0.0, 2.0, 0.0) == ("none", 1.0)


def test_in_and_out_progress():
    tr = TextTransition("fade", "slide", 0.5)
    assert transition_state(tr, 1.0, 3.0, 1.0) == ("fade", 0.0)
    style, p = transition_state(tr, 1.0, 3.0, 1.25)
    assert style == "fade" and 0.0 < p < 1.0
    assert transition_state(tr, 1.0, 3.0, 2.0) == ("none", 1.0)
    style, p = transition_state(tr, 1.0, 3.0, 2.75)
    assert style == "slide" and 0.0 < p < 1.0
    assert transition_state(tr, 1.0, 3.0, 3.0)[1] == 0.0


def test_duration_capped_to_half_of_short_captions():
    tr = TextTransition("fade", "fade", 1.0)
    # 0.4s caption -> each transition takes at most 0.2s, so the midpoint is fully shown
    assert transition_state(tr, 0.0, 0.4, 0.2) == ("none", 1.0)


def test_visible_window_lingers_until_next_segment():
    a, b, c = _seg(0.0, 1.0), _seg(1.2, 2.0), _seg(5.0, 6.0)
    segs = [a, b, c]
    assert _visible_window(segs, a) == (0.0, 1.2)   # next starts within linger
    assert _visible_window(segs, b) == (1.2, 2.4)   # full 0.4s linger
    assert _visible_window(segs, c) == (5.0, 6.4)   # last segment
    overlapping = [_seg(0.0, 1.0), _seg(0.5, 2.0)]
    assert _visible_window(overlapping, overlapping[0]) == (0.0, 1.0)


def _caption(w=100, h=20):
    return Image.new("RGBA", (w, h), (255, 0, 0, 255))


def test_composite_fade_halfway():
    frame = Image.new("RGBA", (100, 60), (0, 0, 0, 255))
    out = composite_caption(frame, _caption(), 40, "fade", 0.5)
    assert out.getpixel((50, 50))[0] in (127, 128)
    assert out.getpixel((50, 10)) == (0, 0, 0, 255)


def test_composite_slide_rises_from_bottom():
    frame = Image.new("RGBA", (100, 60), (0, 0, 0, 255))
    out = composite_caption(frame, _caption(), 40, "slide", 0.5)
    assert out.getpixel((50, 45)) == (0, 0, 0, 255)      # not yet risen this far
    assert out.getpixel((50, 55)) == (255, 0, 0, 255)


def test_composite_zoom_shrinks_towards_centre():
    frame = Image.new("RGBA", (100, 60), (0, 0, 0, 255))
    out = composite_caption(frame, _caption(), 40, "zoom", 0.5)
    assert out.getpixel((2, 50)) == (0, 0, 0, 255)       # edges uncovered while small
    assert out.getpixel((50, 50))[0] > 0


def test_composite_hidden_and_full():
    for style in ("fade", "slide", "zoom"):
        frame = Image.new("RGBA", (100, 60), (0, 0, 0, 255))
        assert composite_caption(frame, _caption(), 40, style, 0.0).getpixel((50, 50)) == (0, 0, 0, 255)
        frame = Image.new("RGBA", (100, 60), (0, 0, 0, 255))
        assert composite_caption(frame, _caption(), 40, style, 1.0).getpixel((50, 50)) == (255, 0, 0, 255)


def test_render_frame_fade_in_starts_hidden():
    bg = Image.new("RGBA", (200, 120), (10, 20, 30, 255))
    segs = [_seg(1.0, 3.0, "hello")]
    tr = TextTransition("fade", "fade", 0.3)
    assert render_frame(bg, segs, 1.0, 24, transition=tr).tobytes() == bg.convert("RGB").tobytes()
    assert render_frame(bg, segs, 2.0, 24, transition=tr).tobytes() != bg.convert("RGB").tobytes()
    # Bar is fully dark mid-caption and has almost faded out by the end of its linger window
    def close(a, b):
        return all(abs(x - y) <= 1 for x, y in zip(a, b))

    assert close(render_frame(bg, segs, 2.0, 24, transition=tr).getpixel((2, 115)), (3, 5, 8))
    assert close(render_frame(bg, segs, 3.399, 24, transition=tr).getpixel((2, 115)), (10, 20, 30))


def test_caption_taller_than_frame_is_clipped():
    segs = [Segment("x", 0.0, 2.0, [Word(w, 0.0, 2.0) for w in "one two three four five six".split()])]
    bg = Image.new("RGBA", (60, 40), (0, 0, 0, 255))
    for style in ("none", "fade", "slide", "zoom"):
        tr = TextTransition(style, style, 0.5)
        for t in (0.1, 1.0, 2.3):
            assert render_frame(bg, segs, t, 40, transition=tr).size == (60, 40)
