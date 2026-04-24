import subprocess
from pathlib import Path
from typing import Dict

_ASSETS_DIR = Path(__file__).parent.parent / "assets" / "fonts"


def discover_fonts() -> Dict[str, str]:
    """Return {display_name: abs_path} for all usable TTF/OTF fonts, sorted."""
    fonts: Dict[str, str] = {}

    # 1. fc-list (Linux/macOS with fontconfig)
    try:
        out = subprocess.run(["fc-list"], capture_output=True, text=True, timeout=10).stdout
        for line in out.splitlines():
            parts = line.strip().split(":")
            if len(parts) < 2:
                continue
            path = parts[0].strip()
            if Path(path).suffix.lower() not in {".ttf", ".otf", ".ttc"}:
                continue
            family = parts[1].strip().split(",")[0].strip()
            style = ""
            for p in parts[2:]:
                if p.strip().startswith("style="):
                    style = p.strip()[6:].split(",")[0].strip()
                    break
            if style and style not in ("Regular", "Book", "Roman", "Medium", ""):
                display = f"{family} {style}"
            else:
                display = family
            if display and Path(path).exists():
                fonts[display] = path
    except Exception:
        pass

    # 2. Directory scan fallback (when fc-list unavailable)
    if not fonts:
        for d in ["/usr/share/fonts", "/Library/Fonts", "C:/Windows/Fonts"]:
            p = Path(d)
            if p.exists():
                for f in p.rglob("*.ttf"):
                    fonts[f.stem.replace("-", " ")] = str(f)

    # 3. Always include bundled fonts (guaranteed fallback)
    if _ASSETS_DIR.exists():
        for f in sorted(_ASSETS_DIR.glob("*.ttf")):
            name = f.stem.replace("-", " ")
            if name not in fonts:
                fonts[name] = str(f)

    return dict(sorted(fonts.items()))
