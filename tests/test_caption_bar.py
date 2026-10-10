import pytest
from PIL import Image

from core.caption_bar import CAPTION_EDGE_STYLES, bar_margins, build_bar
from core.renderer import render_frame
from core.transcriber import Segment, Word


def _alpha_col(bar, x=None):
    x = bar.width // 2 if x is None else x
    return [bar.getpixel((x, y))[3] for y in range(bar.height)]


def test_styles_map_to_ids():
    assert CAPTION_EDGE_STYLES == {
        "Hard": "hard", "Fade": "fade", "Rounded": "rounded", "Feather": "feather",
    }


def test_hard_is_uniform():
    bar, top = build_bar(100, 40, 0.5, "hard", 30)
    assert bar.size == (100, 40) and top == 0
    assert set(_alpha_col(bar)) == {128}


def test_fade_bottom_softens_top_only():
    bar, top = build_bar(100, 40, 1.0, "fade", 20, "bottom")
    col = _alpha_col(bar)
    assert top == 20 and bar.height == 60
    assert col[0] == 0 and col[-1] == 255
    assert col[:20] == sorted(col[:20])
    assert set(col[20:]) == {255}


def test_fade_middle_softens_both():
    assert bar_margins("fade", 10, "middle") == (10, 10)
    assert bar_margins("fade", 10, "top") == (0, 10)


def test_zero_size_matches_hard():
    for style in ("fade", "rounded", "feather"):
        bar, top = build_bar(50, 30, 0.7, style, 0)
        assert bar.size == (50, 30) and set(_alpha_col(bar)) == {178}


def test_rounded_corners_are_transparent():
    bar, _ = build_bar(100, 40, 1.0, "rounded", 12)
    assert bar.getpixel((0, 0))[3] == 0
    assert bar.getpixel((50, 20))[3] == 255


@pytest.mark.parametrize("style", ["hard", "fade", "rounded", "feather"])
@pytest.mark.parametrize("position", ["top", "middle", "bottom"])
def test_render_frame_keeps_size(style, position):
    seg = Segment("hello world", 0.0, 2.0, [Word("hello", 0, 1), Word("world", 1, 2)])
    frame = Image.new("RGB", (320, 180), (200, 200, 200))
    out = render_frame(frame, [seg], 0.5, font_size=24, position=position,
                       bg_edge_style=style, bg_edge_size=30)
    assert out.size == (320, 180)
