#!/usr/bin/env python3
import sys
import tkinter as tk


def _check_deps() -> list[str]:
    missing = []
    for pkg, import_name in [
        ("openai-whisper", "whisper"),
        ("moviepy", "moviepy"),
        ("Pillow", "PIL"),
        ("numpy", "numpy"),
    ]:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pkg)
    return missing


def main() -> None:
    missing = _check_deps()
    if missing:
        print("Missing required packages. Install them with:")
        print(f"  pip install {' '.join(missing)}")
        print("\nOr install all at once:")
        print("  pip install -r requirements.txt")
        sys.exit(1)

    root = tk.Tk()
    from gui.app import AudiogrammerApp
    app = AudiogrammerApp(root)  # noqa: F841
    root.mainloop()


if __name__ == "__main__":
    main()
