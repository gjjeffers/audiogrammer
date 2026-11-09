#!/usr/bin/env python3.12
import sys
import traceback
import tkinter as tk
from tkinter import messagebox

# Packages the app cannot run without: (pip name, import name).
REQUIRED_PACKAGES = [
    ("openai-whisper", "whisper"),
    ("moviepy", "moviepy"),
    ("Pillow", "PIL"),
    ("numpy", "numpy"),
]


def _is_frozen() -> bool:
    """True when running from a PyInstaller-built EXE."""
    return bool(getattr(sys, "frozen", False))


def _check_deps() -> list[tuple[str, str]]:
    """Try importing every required package.

    Returns (pip name, formatted traceback) for each one that fails. Any
    exception counts, not just ImportError: a bundled package can fail with
    OSError (DLL load failure) or similar, and the real traceback is the only
    useful clue as to why.
    """
    failures = []
    for pkg, import_name in REQUIRED_PACKAGES:
        try:
            __import__(import_name)
        except Exception:
            failures.append((pkg, traceback.format_exc()))
    return failures


def _report_failures(failures: list[tuple[str, str]]) -> None:
    names = ", ".join(pkg for pkg, _ in failures)
    details = "\n".join(f"--- {pkg} ---\n{tb}" for pkg, tb in failures)

    if _is_frozen():
        # Everything is supposed to be bundled in the EXE, so "pip install" is
        # the wrong advice here. Show the real error so it can be reported.
        message = (
            f"Audiogrammer could not load a bundled component: {names}.\n\n"
            "This is a problem with this build of the EXE, not with your "
            "system. Please report it at "
            "https://github.com/gjjeffers/audiogrammer/issues and include "
            "the details below.\n\n" + details
        )
        print(message, file=sys.stderr)
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Audiogrammer - failed to start", message[:3000])
            root.destroy()
        except Exception:
            pass  # console output above is the fallback
    else:
        missing = " ".join(pkg for pkg, _ in failures)
        print("Missing or broken required packages. Install them with:")
        print(f"  pip install {missing}")
        print("\nOr install all at once:")
        print("  pip install -r requirements.txt")
        print("\nImport errors:\n" + details, file=sys.stderr)


def main() -> None:
    failures = _check_deps()
    if failures:
        _report_failures(failures)
        sys.exit(1)

    root = tk.Tk()
    from gui.app import AudiogrammerApp
    app = AudiogrammerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
