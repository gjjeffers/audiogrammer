import shutil
from pathlib import Path

import core.fonts as fonts
from core.renderer import render_frame
from core.transcriber import Segment, Word
from PIL import Image

_BUNDLED = Path(__file__).parent.parent / "assets" / "fonts" / "LiberationSans-Bold.ttf"


def test_style_weight_parses_weight_and_variant():
    assert fonts.style_weight("Regular") == (400, ())
    assert fonts.style_weight("Book") == (400, ())
    assert fonts.style_weight("Bold Italic") == (700, ("italic",))
    assert fonts.style_weight("SemiBold") == (600, ())
    assert fonts.style_weight("Extra Bold") == (800, ())
    assert fonts.style_weight("Condensed Black Oblique") == (900, ("condensed", "oblique"))


def test_weight_options_cover_font_default_and_css_scale():
    assert fonts.FONT_WEIGHTS[fonts.FONT_DEFAULT_WEIGHT] is None
    assert [w for w in fonts.FONT_WEIGHTS.values() if w] == list(range(100, 1000, 100))


def test_nearest_face_prefers_heavier_on_tie():
    faces = [(300, "light"), (500, "medium")]
    assert fonts._nearest_face(faces, 400) == (500, "medium")
    assert fonts._nearest_face(faces, 100) == (300, "light")


def test_default_weight_loads_face_unchanged():
    font, stroke = fonts.load_weighted_font(str(_BUNDLED), 40, None)
    assert font.getname() == ("Liberation Sans", "Bold")
    assert stroke == 0


def test_heavier_than_available_adds_synthetic_stroke(tmp_path):
    path = tmp_path / "LiberationSans-Bold.ttf"
    shutil.copy(_BUNDLED, path)
    _, stroke_bold = fonts.load_weighted_font(str(path), 100, 700)
    _, stroke_black = fonts.load_weighted_font(str(path), 100, 900)
    _, stroke_light = fonts.load_weighted_font(str(path), 100, 300)
    assert stroke_bold == 0
    assert stroke_black > 0
    assert stroke_light == 0  # can't go lighter than the lightest face


def test_family_faces_ignores_other_files(tmp_path):
    path = tmp_path / "LiberationSans-Bold.ttf"
    shutil.copy(_BUNDLED, path)
    (tmp_path / "notes.txt").write_text("not a font")
    (tmp_path / "broken.ttf").write_bytes(b"garbage")
    assert fonts._family_faces(str(path)) == [(700, str(path))]


class _FakeVariableFont:
    def __init__(self):
        self.set_to = None

    def get_variation_axes(self):
        return [
            {"name": b"Width", "minimum": 75, "maximum": 100, "default": 100},
            {"name": b"Weight", "minimum": 100, "maximum": 800, "default": 400},
        ]

    def set_variation_by_axes(self, values):
        self.set_to = values


def test_variable_font_weight_axis_is_set_and_clamped():
    font = _FakeVariableFont()
    assert fonts._set_variable_weight(font, 600) == 600
    assert font.set_to == [100, 600]
    assert fonts._set_variable_weight(font, 900) == 800
    assert font.set_to == [100, 800]


def test_static_font_has_no_weight_axis():
    from PIL import ImageFont
    assert fonts._set_variable_weight(ImageFont.truetype(str(_BUNDLED), 20), 700) is None


def test_render_frame_heavier_weight_draws_more_ink(tmp_path):
    path = tmp_path / "LiberationSans-Bold.ttf"
    shutil.copy(_BUNDLED, path)
    seg = Segment("hello world", 0.0, 2.0, [Word("hello", 0.0, 1.0), Word("world", 1.0, 2.0)])
    bg = Image.new("RGBA", (320, 180), (0, 0, 0, 255))

    def ink(weight):
        img = render_frame(bg, [seg], 0.5, 32, (255, 255, 255), (255, 255, 255), None, str(path),
                           font_weight=weight)
        return sum(img.convert("L").histogram()[129:])

    assert ink(900) > ink(None)
