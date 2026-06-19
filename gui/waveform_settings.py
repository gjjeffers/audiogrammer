import tkinter as tk
from tkinter import colorchooser, ttk

_STRETCH_POSITIONS = ["Top", "Middle", "Bottom"]
_TILE_POSITIONS = [
    "Top Left", "Top Center", "Top Right",
    "Middle Left", "Middle Center", "Middle Right",
    "Bottom Left", "Bottom Center", "Bottom Right",
]


class WaveformSettingsDialog(tk.Toplevel):
    """Modal dialog editing the app's shared wf_* tk.Vars in place."""

    def __init__(self, parent: tk.Tk, app) -> None:
        super().__init__(parent)
        self.app = app
        self.title("Waveform Settings")
        self.resizable(False, False)
        self.transient(parent)
        self.update_idletasks()  # ensure mapped before grab on X11
        self.grab_set()

        self._build_ui()
        self._on_placement_changed()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build_ui(self) -> None:
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Checkbutton(
            frm, text="Enable waveform overlay", variable=self.app.wf_enabled,
        ).grid(row=0, column=0, columnspan=4, sticky=tk.W, pady=(0, 8))

        # Mode + Style
        ttk.Label(frm, text="Mode:").grid(row=1, column=0, sticky=tk.W, padx=(0, 6), pady=4)
        ttk.Combobox(
            frm, textvariable=self.app.wf_mode, state="readonly", width=12,
            values=["Reactive", "Progress"],
        ).grid(row=1, column=1, sticky=tk.W, pady=4)
        ttk.Label(frm, text="Style:").grid(row=1, column=2, sticky=tk.W, padx=(12, 6), pady=4)
        ttk.Combobox(
            frm, textvariable=self.app.wf_style, state="readonly", width=13,
            values=["Line", "Rounded Bars", "Circular"],
        ).grid(row=1, column=3, sticky=tk.W, pady=4)

        # Colors
        ttk.Label(frm, text="Color:").grid(row=2, column=0, sticky=tk.W, padx=(0, 6), pady=4)
        self._color_btn = tk.Button(
            frm, bg=self.app.wf_color, width=5, relief=tk.GROOVE,
            command=self._pick_color,
        )
        self._color_btn.grid(row=2, column=1, sticky=tk.W, pady=4)

        ttk.Checkbutton(
            frm, text="Gradient", variable=self.app.wf_use_gradient,
        ).grid(row=2, column=2, sticky=tk.W, padx=(12, 0), pady=4)
        self._grad_btn = tk.Button(
            frm, bg=self.app.wf_gradient_color, width=5, relief=tk.GROOVE,
            command=self._pick_gradient,
        )
        self._grad_btn.grid(row=2, column=3, sticky=tk.W, pady=4)

        # Placement + Position
        ttk.Label(frm, text="Placement:").grid(row=3, column=0, sticky=tk.W, padx=(0, 6), pady=4)
        self._placement_cb = ttk.Combobox(
            frm, textvariable=self.app.wf_placement, state="readonly", width=12,
            values=["Stretch", "Tile"],
        )
        self._placement_cb.grid(row=3, column=1, sticky=tk.W, pady=4)
        self._placement_cb.bind("<<ComboboxSelected>>", self._on_placement_changed)

        ttk.Label(frm, text="Position:").grid(row=3, column=2, sticky=tk.W, padx=(12, 6), pady=4)
        self._position_cb = ttk.Combobox(
            frm, textvariable=self.app.wf_position, state="readonly", width=13,
        )
        self._position_cb.grid(row=3, column=3, sticky=tk.W, pady=4)

        # Bar count + thickness
        ttk.Label(frm, text="Bar count:").grid(row=4, column=0, sticky=tk.W, padx=(0, 6), pady=4)
        ttk.Spinbox(
            frm, textvariable=self.app.wf_bar_count, from_=8, to=200, width=6,
        ).grid(row=4, column=1, sticky=tk.W, pady=4)
        ttk.Label(frm, text="Line width:").grid(row=4, column=2, sticky=tk.W, padx=(12, 6), pady=4)
        ttk.Spinbox(
            frm, textvariable=self.app.wf_thickness, from_=1, to=20, width=6,
        ).grid(row=4, column=3, sticky=tk.W, pady=4)

        # Opacity
        ttk.Label(frm, text="Opacity:").grid(row=5, column=0, sticky=tk.W, padx=(0, 6), pady=4)
        ttk.Scale(
            frm, variable=self.app.wf_opacity, from_=0, to=100,
            orient=tk.HORIZONTAL, length=140,
        ).grid(row=5, column=1, columnspan=2, sticky=tk.W, pady=4)
        self._opacity_lbl = ttk.Label(frm, width=5)
        self._opacity_lbl.grid(row=5, column=3, sticky=tk.W)
        self.app.wf_opacity.trace_add("write", self._update_opacity_lbl)
        self._update_opacity_lbl()

        # Sensitivity
        ttk.Label(frm, text="Sensitivity:").grid(row=6, column=0, sticky=tk.W, padx=(0, 6), pady=4)
        ttk.Scale(
            frm, variable=self.app.wf_sensitivity, from_=0.2, to=3.0,
            orient=tk.HORIZONTAL, length=140,
        ).grid(row=6, column=1, columnspan=2, sticky=tk.W, pady=4)
        self._sens_lbl = ttk.Label(frm, width=5)
        self._sens_lbl.grid(row=6, column=3, sticky=tk.W)
        self.app.wf_sensitivity.trace_add("write", self._update_sens_lbl)
        self._update_sens_lbl()

        # Smoothing
        ttk.Label(frm, text="Smoothing:").grid(row=7, column=0, sticky=tk.W, padx=(0, 6), pady=4)
        ttk.Scale(
            frm, variable=self.app.wf_smoothing, from_=0.0, to=0.95,
            orient=tk.HORIZONTAL, length=140,
        ).grid(row=7, column=1, columnspan=2, sticky=tk.W, pady=4)
        self._smooth_lbl = ttk.Label(frm, width=5)
        self._smooth_lbl.grid(row=7, column=3, sticky=tk.W)
        self.app.wf_smoothing.trace_add("write", self._update_smooth_lbl)
        self._update_smooth_lbl()
        ttk.Label(frm, text="(reactive mode only)", foreground="#888888").grid(
            row=8, column=1, columnspan=3, sticky=tk.W
        )

        # Mirror
        ttk.Checkbutton(
            frm, text="Mirror (symmetric reflection)", variable=self.app.wf_mirror,
        ).grid(row=9, column=0, columnspan=4, sticky=tk.W, pady=(6, 4))

        ttk.Button(frm, text="Close", command=self._close).grid(
            row=10, column=3, sticky=tk.E, pady=(8, 0)
        )

    # ---- handlers --------------------------------------------------------

    def _on_placement_changed(self, _event=None) -> None:
        if self.app.wf_placement.get() == "Tile":
            self._position_cb.config(values=_TILE_POSITIONS)
            if self.app.wf_position.get() not in _TILE_POSITIONS:
                self.app.wf_position.set("Bottom Center")
        else:
            self._position_cb.config(values=_STRETCH_POSITIONS)
            if self.app.wf_position.get() not in _STRETCH_POSITIONS:
                self.app.wf_position.set("Bottom")

    def _pick_color(self) -> None:
        result = colorchooser.askcolor(color=self.app.wf_color, title="Waveform color")
        if result and result[1]:
            self.app.wf_color = result[1]
            self._color_btn.config(bg=result[1])

    def _pick_gradient(self) -> None:
        result = colorchooser.askcolor(color=self.app.wf_gradient_color, title="Gradient color")
        if result and result[1]:
            self.app.wf_gradient_color = result[1]
            self._grad_btn.config(bg=result[1])

    def _update_opacity_lbl(self, *_) -> None:
        self._opacity_lbl.config(text=f"{int(self.app.wf_opacity.get())}%")

    def _update_sens_lbl(self, *_) -> None:
        self._sens_lbl.config(text=f"{self.app.wf_sensitivity.get():.1f}×")

    def _update_smooth_lbl(self, *_) -> None:
        self._smooth_lbl.config(text=f"{self.app.wf_smoothing.get():.2f}")

    def _close(self) -> None:
        self.grab_release()
        self.destroy()
