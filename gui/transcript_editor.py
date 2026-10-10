import tkinter as tk
from tkinter import scrolledtext, ttk
from typing import Callable, List

from core.transcriber import Segment
from core.transcript_edits import apply_edits, header


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
        self.geometry("680x640")
        self.minsize(520, 420)
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
                 "Edit the text freely. Header lines [M:SS.cc – M:SS.cc] set when each caption is shown —\n"
                 "change the times to move a caption.",
            justify=tk.LEFT,
            wraplength=640,
        ).pack(anchor=tk.W)

        # Pack the button bar first (anchored to the bottom) so it always keeps
        # its space; the text area then takes whatever remains.
        btn_bar = ttk.Frame(self, padding=(12, 4, 12, 10))
        btn_bar.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Button(btn_bar, text="Update Transcript", command=self._do_render).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(btn_bar, text="Cancel", command=self._do_cancel).pack(side=tk.RIGHT)

        self._text = scrolledtext.ScrolledText(
            self, wrap=tk.WORD, font=("TkFixedFont", 11), relief=tk.SUNKEN, borderwidth=1,
            height=10,
        )
        self._text.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        # Style header lines as grey and slightly smaller
        self._text.tag_configure("header", foreground="#888888", font=("TkFixedFont", 10))

        self._populate()

    def _populate(self) -> None:
        self._text.delete("1.0", tk.END)
        for seg in self._segments:
            hdr = header(seg) + "\n"
            self._text.insert(tk.END, hdr, "header")
            self._text.insert(tk.END, seg.text + "\n\n")

    def _do_render(self) -> None:
        edited_text = self._text.get("1.0", tk.END)
        edited_segments = apply_edits(self._segments, edited_text)
        self.grab_release()
        self.destroy()
        self._on_render(edited_segments)

    def _do_cancel(self) -> None:
        self.grab_release()
        self.destroy()
        self._on_cancel()
