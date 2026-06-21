import tkinter as tk
from tkinter import scrolledtext, ttk
from typing import Callable, List

from core.transcriber import Segment, Word


def _fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def _segments_to_text(segments: List[Segment]) -> str:
    lines = []
    for seg in segments:
        lines.append(f"[{_fmt_time(seg.start)} – {_fmt_time(seg.end)}]")
        lines.append(seg.text)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _apply_edits(original: List[Segment], edited_text: str) -> List[Segment]:
    """Reconcile edited plain text back into the original segment list.

    Each segment block is delimited by a [M:SS – M:SS] header line.
    Within each block the user may have changed word text but headers are
    kept intact. Word count changes trigger proportional timestamp redistribution.
    """
    # Split into blocks by header lines
    blocks: List[str] = []
    current: List[str] = []
    for line in edited_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and "–" in stripped and stripped.endswith("]"):
            if current:
                blocks.append("\n".join(current).strip())
                current = []
        else:
            current.append(line)
    if current:
        blocks.append("\n".join(current).strip())

    result: List[Segment] = []
    for i, seg in enumerate(original):
        edited_block = blocks[i] if i < len(blocks) else ""
        edited_words = edited_block.split() if edited_block.strip() else []

        if not edited_words:
            result.append(seg)
            continue

        n = len(edited_words)
        if n == len(seg.words):
            # Same count — preserve timestamps exactly
            new_words = [
                Word(text=w, start=orig.start, end=orig.end)
                for w, orig in zip(edited_words, seg.words)
            ]
        else:
            # Count changed — distribute proportionally
            dur = seg.end - seg.start
            new_words = [
                Word(
                    text=w,
                    start=seg.start + idx * dur / n,
                    end=seg.start + (idx + 1) * dur / n,
                )
                for idx, w in enumerate(edited_words)
            ]

        result.append(Segment(
            text=" ".join(edited_words),
            start=seg.start,
            end=seg.end,
            words=new_words,
        ))

    return result


class TranscriptEditorDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Tk,
        segments: List[Segment],
        on_render: Callable[[List[Segment]], None],
        on_cancel: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self.title("Review Transcript")
        self.geometry("680x520")
        self.resizable(True, True)
        self.transient(parent)
        self.update_idletasks()  # ensure window is mapped before grab_set on X11
        self.grab_set()

        self._segments = segments
        self._on_render = on_render
        self._on_cancel = on_cancel

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._do_cancel)

    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=(12, 10, 12, 4))
        top.pack(fill=tk.X)
        ttk.Label(
            top,
            text="Review and correct the transcript below. Each block is one Whisper segment.\n"
                 "Edit the text lines freely — header lines [M:SS – M:SS] mark segment boundaries.",
            justify=tk.LEFT,
            wraplength=640,
        ).pack(anchor=tk.W)

        self._text = scrolledtext.ScrolledText(
            self, wrap=tk.WORD, font=("TkFixedFont", 11), relief=tk.SUNKEN, borderwidth=1
        )
        self._text.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        # Style header lines as grey and slightly smaller
        self._text.tag_configure("header", foreground="#888888", font=("TkFixedFont", 10))

        self._populate()

        btn_bar = ttk.Frame(self, padding=(12, 4, 12, 10))
        btn_bar.pack(fill=tk.X)
        ttk.Button(btn_bar, text="Update Transcript", command=self._do_render).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(btn_bar, text="Cancel", command=self._do_cancel).pack(side=tk.RIGHT)

    def _populate(self) -> None:
        self._text.delete("1.0", tk.END)
        for seg in self._segments:
            header = f"[{_fmt_time(seg.start)} – {_fmt_time(seg.end)}]\n"
            self._text.insert(tk.END, header, "header")
            self._text.insert(tk.END, seg.text + "\n\n")

    def _do_render(self) -> None:
        edited_text = self._text.get("1.0", tk.END)
        edited_segments = _apply_edits(self._segments, edited_text)
        self.grab_release()
        self.destroy()
        self._on_render(edited_segments)

    def _do_cancel(self) -> None:
        self.grab_release()
        self.destroy()
        self._on_cancel()
