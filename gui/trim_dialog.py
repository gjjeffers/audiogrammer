import threading
import tkinter as tk
from tkinter import ttk

from core.trim import clamp_range, format_timecode, parse_timecode

_OVERVIEW_W = 560
_OVERVIEW_H = 90
_DETAIL_W = 270
_DETAIL_H = 70
_DETAIL_WINDOW = 3.0   # seconds shown on each side of a handle in detail strips
_BUCKETS = 560


class TrimDialog(tk.Toplevel):
    """Modal in/out trim selector editing the app's shared trim vars in place."""

    def __init__(self, parent: tk.Tk, app) -> None:
        super().__init__(parent)
        self.app = app
        self.title("Trim Audio")
        self.resizable(False, False)
        self.transient(parent)
        self.update_idletasks()
        self.grab_set()

        self._envelope = None          # np.ndarray 0..1 or None until analyzed
        self._duration = 0.0
        self._drag_handle = None       # "start" | "end" | None
        self._detail_anchor = None

        self._build_ui()
        self._traces = [
            self.app.trim_start.trace_add("write", self._on_vars_changed),
            self.app.trim_end.trace_add("write", self._on_vars_changed),
        ]
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._load_overview()

    # ---- UI --------------------------------------------------------------

    def _build_ui(self) -> None:
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        self._status = ttk.Label(frm, text="Analyzing audio…")
        self._status.grid(row=0, column=0, columnspan=4, sticky=tk.W, pady=(0, 6))

        self._overview = tk.Canvas(frm, width=_OVERVIEW_W, height=_OVERVIEW_H,
                                   bg="#1e1e1e", highlightthickness=0)
        self._overview.grid(row=1, column=0, columnspan=4, pady=(0, 8))
        self._overview.bind("<Button-1>", self._on_overview_press)
        self._overview.bind("<B1-Motion>", self._on_overview_drag)
        self._overview.bind("<ButtonRelease-1>", lambda e: setattr(self, "_drag_handle", None))

        # Detail strips
        ttk.Label(frm, text="In point").grid(row=2, column=0, sticky=tk.W)
        ttk.Label(frm, text="Out point").grid(row=2, column=2, sticky=tk.W)
        self._detail_in = tk.Canvas(frm, width=_DETAIL_W, height=_DETAIL_H,
                                    bg="#1e1e1e", highlightthickness=0)
        self._detail_in.grid(row=3, column=0, columnspan=2, padx=(0, 8), pady=(0, 8))
        self._detail_out = tk.Canvas(frm, width=_DETAIL_W, height=_DETAIL_H,
                                     bg="#1e1e1e", highlightthickness=0)
        self._detail_out.grid(row=3, column=2, columnspan=2, pady=(0, 8))
        self._detail_in.bind("<Button-1>", lambda e: self._on_detail_press("start", e))
        self._detail_in.bind("<B1-Motion>", lambda e: self._on_detail_drag("start", e))
        self._detail_in.bind("<ButtonRelease-1>", lambda e: setattr(self, "_detail_anchor", None))
        self._detail_out.bind("<Button-1>", lambda e: self._on_detail_press("end", e))
        self._detail_out.bind("<B1-Motion>", lambda e: self._on_detail_drag("end", e))
        self._detail_out.bind("<ButtonRelease-1>", lambda e: setattr(self, "_detail_anchor", None))

        # Numeric fields + nudges
        self._in_var = tk.StringVar()
        self._out_var = tk.StringVar()
        self._build_numeric_row(frm, 4, "In:", self._in_var, "start")
        self._build_numeric_row(frm, 5, "Out:", self._out_var, "end")

        self._readout = ttk.Label(frm, text="")
        self._readout.grid(row=6, column=0, columnspan=4, sticky=tk.W, pady=(4, 6))

        btns = ttk.Frame(frm)
        btns.grid(row=7, column=0, columnspan=4, sticky=tk.EW)
        ttk.Button(btns, text="Use Full Audio", command=self._use_full).pack(side=tk.LEFT)
        ttk.Button(btns, text="Close", command=self._close).pack(side=tk.RIGHT)

    def _build_numeric_row(self, frm, row, label, var, which) -> None:
        ttk.Label(frm, text=label).grid(row=row, column=0, sticky=tk.W, pady=2)
        entry = ttk.Entry(frm, textvariable=var, width=10)
        entry.grid(row=row, column=1, sticky=tk.W, pady=2)
        entry.bind("<Return>", lambda e: self._commit_numeric(var, which))
        entry.bind("<FocusOut>", lambda e: self._commit_numeric(var, which))
        nudge = ttk.Frame(frm)
        nudge.grid(row=row, column=2, columnspan=2, sticky=tk.W)
        for label_text, delta in [("-1s", -1.0), ("-0.1s", -0.1), ("+0.1s", 0.1), ("+1s", 1.0)]:
            ttk.Button(nudge, text=label_text, width=5,
                       command=lambda d=delta, w=which: self._nudge(w, d)).pack(side=tk.LEFT, padx=1)

    # ---- overview analysis (background thread) ---------------------------

    def _load_overview(self) -> None:
        path = self.app.audio_path.get().strip()
        if not path:
            self._status.config(text="No audio file selected.")
            return
        cached = self.app._overview_cache.get(path)
        if cached is not None:
            self._on_overview_ready(*cached)
            return

        def work():
            from core.waveform import load_audio_overview
            try:
                env, dur = load_audio_overview(path, _BUCKETS)
            except Exception as exc:  # pragma: no cover - I/O failure path
                error_text = f"Could not read audio: {exc}"
                self.after(0, lambda: self._status.config(text=error_text))
                return
            self.after(0, lambda: self._on_overview_ready(env, dur, path))

        threading.Thread(target=work, daemon=True).start()

    def _on_overview_ready(self, env, dur, path=None) -> None:
        if path is not None:
            self.app._overview_cache[path] = (env, dur)
        self._envelope = env
        self._duration = dur
        self.app._audio_duration = dur
        if not self.app.trim_enabled.get() or self.app.trim_end.get() <= 0:
            self.app.trim_start.set(0.0)
            self.app.trim_end.set(dur)
        self._status.config(text=f"Drag the handles or type exact times. Duration {format_timecode(dur)}.")
        self._sync_from_vars()

    # ---- selection editing ----------------------------------------------

    def _set_range(self, start, end) -> None:
        start, end = clamp_range(start, end, self._duration)
        self.app.trim_enabled.set(True)
        self.app.trim_start.set(start)
        self.app.trim_end.set(end)

    def _commit_numeric(self, var, which) -> None:
        val = parse_timecode(var.get())
        if val is None:
            self._sync_from_vars()
            return
        if which == "start":
            self._set_range(val, self.app.trim_end.get())
        else:
            self._set_range(self.app.trim_start.get(), val)

    def _nudge(self, which, delta) -> None:
        if which == "start":
            self._set_range(self.app.trim_start.get() + delta, self.app.trim_end.get())
        else:
            self._set_range(self.app.trim_start.get(), self.app.trim_end.get() + delta)

    def _use_full(self) -> None:
        self.app.trim_enabled.set(False)
        self.app.trim_start.set(0.0)
        self.app.trim_end.set(self._duration)
        self._sync_from_vars()

    def _x_to_time(self, x) -> float:
        if self._duration <= 0:
            return 0.0
        return max(0.0, min(self._duration, (x / _OVERVIEW_W) * self._duration))

    def _on_overview_press(self, event) -> None:
        t = self._x_to_time(event.x)
        mid = (self.app.trim_start.get() + self.app.trim_end.get()) / 2
        self._drag_handle = "start" if t < mid else "end"
        self._on_overview_drag(event)

    def _on_overview_drag(self, event) -> None:
        if self._drag_handle is None:
            return
        t = self._x_to_time(event.x)
        if self._drag_handle == "start":
            self._set_range(t, self.app.trim_end.get())
        else:
            self._set_range(self.app.trim_start.get(), t)

    def _on_detail_press(self, which, event) -> None:
        self._detail_anchor = (
            self.app.trim_start.get() if which == "start" else self.app.trim_end.get()
        )
        self._on_detail_drag(which, event)

    def _on_detail_drag(self, which, event) -> None:
        anchor = self._detail_anchor
        if anchor is None:
            anchor = self.app.trim_start.get() if which == "start" else self.app.trim_end.get()
        lo = anchor - _DETAIL_WINDOW
        frac = max(0.0, min(1.0, event.x / _DETAIL_W))
        t = lo + frac * (2 * _DETAIL_WINDOW)
        if which == "start":
            self._set_range(t, self.app.trim_end.get())
        else:
            self._set_range(self.app.trim_start.get(), t)

    # ---- rendering -------------------------------------------------------

    def _on_vars_changed(self, *_) -> None:
        self._sync_from_vars()

    def _sync_from_vars(self) -> None:
        s = self.app.trim_start.get()
        e = self.app.trim_end.get()
        self._in_var.set(format_timecode(s))
        self._out_var.set(format_timecode(e))
        self._readout.config(
            text=f"Selection: {format_timecode(e - s)}  (of {format_timecode(self._duration)})"
        )
        self._draw_overview()
        self._draw_detail(self._detail_in, s)
        self._draw_detail(self._detail_out, e)

    def _draw_envelope(self, canvas, env_slice, w, h) -> None:
        n = len(env_slice)
        if n == 0:
            return
        mid = h / 2
        step = w / n
        for i, lv in enumerate(env_slice):
            x = i * step
            half = (h / 2) * float(lv)
            canvas.create_line(x, mid - half, x, mid + half, fill="#4a90d9")

    def _draw_overview(self) -> None:
        c = self._overview
        c.delete("all")
        if self._envelope is None:
            return
        self._draw_envelope(c, self._envelope, _OVERVIEW_W, _OVERVIEW_H)
        if self._duration <= 0:
            return
        x0 = (self.app.trim_start.get() / self._duration) * _OVERVIEW_W
        x1 = (self.app.trim_end.get() / self._duration) * _OVERVIEW_W
        c.create_rectangle(0, 0, x0, _OVERVIEW_H, fill="#000000", stipple="gray50", outline="")
        c.create_rectangle(x1, 0, _OVERVIEW_W, _OVERVIEW_H, fill="#000000", stipple="gray50", outline="")
        for x in (x0, x1):
            c.create_line(x, 0, x, _OVERVIEW_H, fill="#ffdc00", width=2)

    def _draw_detail(self, canvas, center_t) -> None:
        canvas.delete("all")
        if self._envelope is None or self._duration <= 0:
            return
        lo = center_t - _DETAIL_WINDOW
        hi = center_t + _DETAIL_WINDOW
        n = len(self._envelope)
        i0 = max(0, int((lo / self._duration) * n))
        i1 = min(n, int((hi / self._duration) * n))
        if i1 > i0:
            self._draw_envelope(canvas, self._envelope[i0:i1], _DETAIL_W, _DETAIL_H)
        canvas.create_line(_DETAIL_W / 2, 0, _DETAIL_W / 2, _DETAIL_H, fill="#ffdc00", width=2)

    # ---- teardown --------------------------------------------------------

    def _close(self) -> None:
        self.app.trim_start.trace_remove("write", self._traces[0])
        self.app.trim_end.trace_remove("write", self._traces[1])
        self.grab_release()
        self.destroy()
