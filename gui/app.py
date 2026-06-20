import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

from core import settings as _settings

# (target_size, suggested_font_size)
_RESOLUTIONS = {
    "Native (source size)":       (None, 40),
    "Square 1080×1080 (1:1)":     ((1080, 1080), 64),
    "720p 1280×720 (16:9)":       ((1280, 720), 52),
    "1080p 1920×1080 (16:9)":     ((1920, 1080), 72),
    "Vertical 1080×1920 (9:16)":  ((1080, 1920), 64),
}

# (crf, x264_preset)
_QUALITIES = {
    "Fast":     (28, "veryfast"),
    "Balanced": (23, "medium"),
    "High":     (18, "slow"),
}


def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


class AudiogrammerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Audiogrammer")
        self.root.geometry("620x860")
        self.root.resizable(True, True)

        try:
            style = ttk.Style()
            style.theme_use("clam")
        except Exception:
            pass

        # ---- State --------------------------------------------------------
        self.bg_path = tk.StringVar()
        self.audio_path = tk.StringVar()
        self.output_path = tk.StringVar(value="audiogram.mp4")
        self.model_size = tk.StringVar(value="base")
        self.font_size = tk.IntVar(value=72)
        self.fps = tk.IntVar(value=24)
        self.resolution = tk.StringVar(value="1080p 1920×1080 (16:9)")
        self.quality = tk.StringVar(value="High")
        self.review_transcript = tk.BooleanVar(value=False)
        self.font_name = tk.StringVar(value="")
        self._font_map: dict = {}
        self._preview_photo = None
        self.text_color = "#FFFFFF"
        self.highlight_color = "#FFDC00"

        # Watermark state
        self.wm_text = tk.StringVar()
        self.wm_image_path = tk.StringVar()
        self.wm_position = tk.StringVar(value="Bottom Right")
        self.wm_opacity = tk.DoubleVar(value=70.0)
        self.wm_font_size = tk.IntVar(value=28)
        self.wm_color = "#FFFFFF"

        # Waveform state (edited via the Waveform Settings dialog)
        self.wf_enabled = tk.BooleanVar(value=False)
        self.wf_mode = tk.StringVar(value="Reactive")
        self.wf_style = tk.StringVar(value="Rounded Bars")
        self.wf_opacity = tk.DoubleVar(value=90.0)
        self.wf_placement = tk.StringVar(value="Stretch")
        self.wf_position = tk.StringVar(value="Bottom")
        self.wf_sensitivity = tk.DoubleVar(value=1.0)
        self.wf_smoothing = tk.DoubleVar(value=0.5)
        self.wf_mirror = tk.BooleanVar(value=False)
        self.wf_bar_count = tk.IntVar(value=48)
        self.wf_thickness = tk.IntVar(value=3)
        self.wf_use_gradient = tk.BooleanVar(value=False)
        self.wf_color = "#FFFFFF"
        self.wf_gradient_color = "#00BFFF"

        # Trim state (edited via the Trim Audio dialog)
        self.trim_enabled = tk.BooleanVar(value=False)
        self.trim_start = tk.DoubleVar(value=0.0)
        self.trim_end = tk.DoubleVar(value=0.0)
        self._audio_duration = 0.0
        self._overview_cache: dict = {}

        self._queue: queue.Queue = queue.Queue()
        self._running = False
        self._cancel_event = threading.Event()
        self._transcript_ready = threading.Event()
        self._edited_segments = None

        self._build_ui()
        self._poll()
        _loaded = _settings.load()
        self._pending_font_name = _loaded.get("font_name", "")
        self._apply_settings(_loaded)
        threading.Thread(target=self._load_fonts_async, daemon=True).start()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root_frame = ttk.Frame(self.root, padding=14)
        root_frame.pack(fill=tk.BOTH, expand=True)

        # ---- Input files -------------------------------------------------
        files = ttk.LabelFrame(root_frame, text="Input Files", padding=8)
        files.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(files, text="Background:").grid(row=0, column=0, sticky=tk.W, padx=(0, 6), pady=4)
        ttk.Entry(files, textvariable=self.bg_path).grid(row=0, column=1, sticky=tk.EW, padx=(0, 4), pady=4)
        ttk.Button(files, text="Browse…", command=self._browse_bg).grid(row=0, column=2, pady=4)

        ttk.Label(files, text="Audio File:").grid(row=1, column=0, sticky=tk.W, padx=(0, 6), pady=4)
        ttk.Entry(files, textvariable=self.audio_path).grid(row=1, column=1, sticky=tk.EW, padx=(0, 4), pady=4)
        ttk.Button(files, text="Browse…", command=self._browse_audio).grid(row=1, column=2, pady=4)

        files.columnconfigure(1, weight=1)

        # ---- Trim launcher ----------------------------------------------
        trim_row = ttk.Frame(root_frame)
        trim_row.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(trim_row, text="Trim Audio…", command=self._open_trim_dialog).pack(side=tk.LEFT)
        self._trim_status_label = ttk.Label(trim_row, text="(full)", foreground="#888888")
        self._trim_status_label.pack(side=tk.LEFT, padx=(8, 0))
        self.trim_enabled.trace_add("write", self._update_trim_status)
        self.trim_start.trace_add("write", self._update_trim_status)
        self.trim_end.trace_add("write", self._update_trim_status)

        # ---- Settings ----------------------------------------------------
        settings = ttk.LabelFrame(root_frame, text="Settings", padding=8)
        settings.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(settings, text="Whisper Model:").grid(row=0, column=0, sticky=tk.W, pady=4, padx=(0, 8))
        model_cb = ttk.Combobox(
            settings,
            textvariable=self.model_size,
            values=["tiny", "base", "small", "medium", "large"],
            width=14,
            state="readonly",
        )
        model_cb.grid(row=0, column=1, sticky=tk.W, pady=4)
        ttk.Label(settings, text="  (larger = more accurate, slower)").grid(row=0, column=2, sticky=tk.W)

        ttk.Checkbutton(
            settings,
            text="Review transcript before rendering",
            variable=self.review_transcript,
        ).grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=4)

        ttk.Label(settings, text="Resolution:").grid(row=2, column=0, sticky=tk.W, pady=4, padx=(0, 8))
        res_cb = ttk.Combobox(
            settings,
            textvariable=self.resolution,
            values=list(_RESOLUTIONS.keys()),
            width=26,
            state="readonly",
        )
        res_cb.grid(row=2, column=1, sticky=tk.W, pady=4)
        res_cb.bind("<<ComboboxSelected>>", self._on_resolution_changed)

        ttk.Label(settings, text="Quality:").grid(row=3, column=0, sticky=tk.W, pady=4, padx=(0, 8))
        ttk.Combobox(
            settings,
            textvariable=self.quality,
            values=list(_QUALITIES.keys()),
            width=14,
            state="readonly",
        ).grid(row=3, column=1, sticky=tk.W, pady=4)
        ttk.Label(settings, text="  (High = CRF 18, slow preset)").grid(row=3, column=2, sticky=tk.W)

        ttk.Label(settings, text="Font:").grid(row=4, column=0, sticky=tk.W, pady=4, padx=(0, 8))
        self._font_cb = ttk.Combobox(
            settings, textvariable=self.font_name,
            values=["(loading fonts…)"], width=26, state="disabled",
        )
        self._font_cb.grid(row=4, column=1, columnspan=2, sticky=tk.W, pady=4)
        self.font_name.trace_add("write", self._update_font_preview)

        self._preview_label = tk.Label(settings, text="", anchor=tk.W, bd=1, relief=tk.SUNKEN)
        self._preview_label.grid(row=5, column=1, columnspan=2, sticky=tk.EW, pady=(0, 6))

        ttk.Label(settings, text="Font Size:").grid(row=6, column=0, sticky=tk.W, pady=4, padx=(0, 8))
        ttk.Spinbox(settings, textvariable=self.font_size, from_=16, to=160, width=6).grid(
            row=6, column=1, sticky=tk.W, pady=4
        )

        ttk.Label(settings, text="Video FPS:").grid(row=7, column=0, sticky=tk.W, pady=4, padx=(0, 8))
        ttk.Spinbox(settings, textvariable=self.fps, from_=12, to=60, width=6).grid(
            row=7, column=1, sticky=tk.W, pady=4
        )

        ttk.Label(settings, text="Text Color:").grid(row=8, column=0, sticky=tk.W, pady=4, padx=(0, 8))
        self._text_color_btn = tk.Button(
            settings, bg=self.text_color, width=5, relief=tk.GROOVE,
            command=self._pick_text_color,
        )
        self._text_color_btn.grid(row=8, column=1, sticky=tk.W, pady=4)

        ttk.Label(settings, text="Highlight Color:").grid(row=9, column=0, sticky=tk.W, pady=4, padx=(0, 8))
        self._highlight_btn = tk.Button(
            settings, bg=self.highlight_color, width=5, relief=tk.GROOVE,
            command=self._pick_highlight_color,
        )
        self._highlight_btn.grid(row=9, column=1, sticky=tk.W, pady=4)

        # ---- Waveform settings launcher ----------------------------------
        wf_row = ttk.Frame(root_frame)
        wf_row.pack(fill=tk.X, pady=(0, 4))
        self._wf_btn = ttk.Button(
            wf_row, text="Waveform Settings…", command=self._open_waveform_settings
        )
        self._wf_btn.pack(side=tk.LEFT)
        self._wf_status_label = ttk.Label(wf_row, text="(off)", foreground="#888888")
        self._wf_status_label.pack(side=tk.LEFT, padx=(8, 0))
        self.wf_enabled.trace_add("write", self._update_wf_status)

        # ---- Output ------------------------------------------------------
        output = ttk.LabelFrame(root_frame, text="Output", padding=8)
        output.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(output, text="Save to:").grid(row=0, column=0, sticky=tk.W, padx=(0, 6), pady=4)
        ttk.Entry(output, textvariable=self.output_path).grid(row=0, column=1, sticky=tk.EW, padx=(0, 4), pady=4)
        ttk.Button(output, text="Browse…", command=self._browse_output).grid(row=0, column=2, pady=4)
        output.columnconfigure(1, weight=1)

        # ---- Watermark -------------------------------------------------------
        wm = ttk.LabelFrame(root_frame, text="Watermark  (leave blank to disable)", padding=8)
        wm.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(wm, text="Text:").grid(row=0, column=0, sticky=tk.W, padx=(0, 6), pady=4)
        ttk.Entry(wm, textvariable=self.wm_text, width=22).grid(row=0, column=1, sticky=tk.EW, padx=(0, 4), pady=4)
        ttk.Label(wm, text="Color:").grid(row=0, column=2, sticky=tk.W, padx=(4, 4))
        self._wm_color_btn = tk.Button(wm, bg=self.wm_color, width=3, relief=tk.GROOVE,
                                       command=self._pick_wm_color)
        self._wm_color_btn.grid(row=0, column=3, padx=(0, 6), pady=4)
        ttk.Label(wm, text="Size:").grid(row=0, column=4, sticky=tk.W)
        ttk.Spinbox(wm, textvariable=self.wm_font_size, from_=10, to=96, width=5).grid(
            row=0, column=5, sticky=tk.W, pady=4)

        ttk.Label(wm, text="Image:").grid(row=1, column=0, sticky=tk.W, padx=(0, 6), pady=4)
        ttk.Entry(wm, textvariable=self.wm_image_path, width=22).grid(row=1, column=1, sticky=tk.EW, padx=(0, 4), pady=4)
        ttk.Button(wm, text="Browse…", command=self._browse_wm_image).grid(row=1, column=2, columnspan=2, sticky=tk.W, pady=4)

        ttk.Label(wm, text="Position:").grid(row=2, column=0, sticky=tk.W, padx=(0, 6), pady=4)
        ttk.Combobox(
            wm, textvariable=self.wm_position,
            values=["Top Left", "Top Right", "Bottom Left", "Bottom Right"],
            width=14, state="readonly",
        ).grid(row=2, column=1, sticky=tk.W, pady=4)

        ttk.Label(wm, text="Opacity:").grid(row=2, column=2, sticky=tk.W, padx=(8, 4))
        ttk.Scale(wm, variable=self.wm_opacity, from_=0, to=100, orient=tk.HORIZONTAL,
                  length=100).grid(row=2, column=3, columnspan=2, sticky=tk.W)
        self._wm_opacity_label = ttk.Label(wm, text="70%", width=4)
        self._wm_opacity_label.grid(row=2, column=5, sticky=tk.W)
        self.wm_opacity.trace_add("write", self._update_opacity_label)

        wm.columnconfigure(1, weight=1)

        # ---- Generate / Cancel buttons -----------------------------------
        btn_row = ttk.Frame(root_frame)
        btn_row.pack(pady=(4, 6))

        self._gen_btn = ttk.Button(btn_row, text="Generate Audiogram", command=self._generate)
        self._gen_btn.pack(side=tk.LEFT, padx=(0, 6))

        self._cancel_btn = ttk.Button(
            btn_row, text="Cancel", command=self._cancel, state=tk.DISABLED
        )
        self._cancel_btn.pack(side=tk.LEFT)

        ttk.Button(btn_row, text="Restore Defaults", command=self._restore_defaults).pack(
            side=tk.LEFT, padx=(6, 0)
        )

        # ---- Progress area -----------------------------------------------
        progress_frame = ttk.Frame(root_frame)
        progress_frame.pack(fill=tk.X)

        self._progress_var = tk.DoubleVar(value=0)
        self._progress_bar = ttk.Progressbar(
            progress_frame, variable=self._progress_var,
            maximum=100, mode="determinate",
        )
        self._progress_bar.pack(fill=tk.X, pady=(0, 4))

        self._status_var = tk.StringVar(value="Ready")
        ttk.Label(progress_frame, textvariable=self._status_var, anchor=tk.W).pack(fill=tk.X)

    # ------------------------------------------------------------------
    # Font discovery
    # ------------------------------------------------------------------

    def _load_fonts_async(self) -> None:
        from core.fonts import discover_fonts
        self._font_map = discover_fonts()
        self.root.after(0, self._on_fonts_loaded)

    def _on_fonts_loaded(self) -> None:
        names = list(self._font_map.keys())
        self._font_cb.config(values=names, state="readonly")
        saved = getattr(self, "_pending_font_name", "")
        if saved and saved in names:
            self.font_name.set(saved)
        else:
            default = next((n for n in names if "Liberation Sans" in n and "Bold" in n), None)
            if default is None:
                default = next((n for n in names if "Sans" in n and "Bold" in n), names[0] if names else "")
            self.font_name.set(default)
        self._update_font_preview()

    def _update_font_preview(self, *_) -> None:
        path = self._font_map.get(self.font_name.get(), "")
        if not path:
            self._preview_label.config(image="", text="")
            return
        sample = "AaBbCcDd 1234"
        try:
            from PIL import Image, ImageDraw, ImageFont, ImageTk
            font = ImageFont.truetype(path, 20)
            dummy = ImageDraw.Draw(Image.new("RGB", (1, 1)))
            bbox = dummy.textbbox((0, 0), sample, font=font)
            w = bbox[2] - bbox[0] + 20
            h = bbox[3] - bbox[1] + 10
            img = Image.new("RGB", (max(w, 1), max(h, 1)), (255, 255, 255))
            ImageDraw.Draw(img).text((10, 5), sample, font=font, fill=(30, 30, 30))
            self._preview_photo = ImageTk.PhotoImage(img)
            self._preview_label.config(image=self._preview_photo, text="")
        except Exception:
            self._preview_label.config(image="", text=sample)

    # ------------------------------------------------------------------
    # Settings persistence
    # ------------------------------------------------------------------

    def _collect_settings(self) -> dict:
        return {
            "audio_path": self.audio_path.get(),
            "bg_path": self.bg_path.get(),
            "output_path": self.output_path.get(),
            "model_size": self.model_size.get(),
            "font_size": self.font_size.get(),
            "fps": self.fps.get(),
            "resolution": self.resolution.get(),
            "quality": self.quality.get(),
            "review_transcript": self.review_transcript.get(),
            "font_name": self.font_name.get(),
            "text_color": self.text_color,
            "highlight_color": self.highlight_color,
            "wm_text": self.wm_text.get(),
            "wm_image_path": self.wm_image_path.get(),
            "wm_position": self.wm_position.get(),
            "wm_opacity": self.wm_opacity.get(),
            "wm_font_size": self.wm_font_size.get(),
            "wm_color": self.wm_color,
            "wf_enabled": self.wf_enabled.get(),
            "wf_mode": self.wf_mode.get(),
            "wf_style": self.wf_style.get(),
            "wf_opacity": self.wf_opacity.get(),
            "wf_placement": self.wf_placement.get(),
            "wf_position": self.wf_position.get(),
            "wf_sensitivity": self.wf_sensitivity.get(),
            "wf_smoothing": self.wf_smoothing.get(),
            "wf_mirror": self.wf_mirror.get(),
            "wf_bar_count": self.wf_bar_count.get(),
            "wf_thickness": self.wf_thickness.get(),
            "wf_use_gradient": self.wf_use_gradient.get(),
            "wf_color": self.wf_color,
            "wf_gradient_color": self.wf_gradient_color,
            "trim_enabled": self.trim_enabled.get(),
            "trim_start": self.trim_start.get(),
            "trim_end": self.trim_end.get(),
        }

    def _apply_settings(self, data: dict) -> None:
        self.audio_path.set(data.get("audio_path", ""))
        self.bg_path.set(data.get("bg_path", ""))
        self.output_path.set(data.get("output_path", "audiogram.mp4"))
        self.model_size.set(data.get("model_size", "base"))
        self.font_size.set(data.get("font_size", 72))
        self.fps.set(data.get("fps", 24))
        self.resolution.set(data.get("resolution", "1080p 1920×1080 (16:9)"))
        self.quality.set(data.get("quality", "High"))
        self.review_transcript.set(data.get("review_transcript", False))
        font_name = data.get("font_name", "")
        if font_name and font_name in self._font_map:
            self.font_name.set(font_name)
        self.text_color = data.get("text_color", "#FFFFFF")
        self._text_color_btn.config(bg=self.text_color)
        self.highlight_color = data.get("highlight_color", "#FFDC00")
        self._highlight_btn.config(bg=self.highlight_color)
        self.wm_text.set(data.get("wm_text", ""))
        self.wm_image_path.set(data.get("wm_image_path", ""))
        self.wm_position.set(data.get("wm_position", "Bottom Right"))
        self.wm_opacity.set(data.get("wm_opacity", 70.0))
        self.wm_font_size.set(data.get("wm_font_size", 28))
        self.wm_color = data.get("wm_color", "#FFFFFF")
        self._wm_color_btn.config(bg=self.wm_color)
        self.wf_enabled.set(data.get("wf_enabled", False))
        self.wf_mode.set(data.get("wf_mode", "Reactive"))
        self.wf_style.set(data.get("wf_style", "Rounded Bars"))
        self.wf_opacity.set(data.get("wf_opacity", 90.0))
        self.wf_placement.set(data.get("wf_placement", "Stretch"))
        self.wf_position.set(data.get("wf_position", "Bottom"))
        self.wf_sensitivity.set(data.get("wf_sensitivity", 1.0))
        self.wf_smoothing.set(data.get("wf_smoothing", 0.5))
        self.wf_mirror.set(data.get("wf_mirror", False))
        self.wf_bar_count.set(data.get("wf_bar_count", 48))
        self.wf_thickness.set(data.get("wf_thickness", 3))
        self.wf_use_gradient.set(data.get("wf_use_gradient", False))
        self.wf_color = data.get("wf_color", "#FFFFFF")
        self.wf_gradient_color = data.get("wf_gradient_color", "#00BFFF")
        self.trim_enabled.set(data.get("trim_enabled", False))
        self.trim_start.set(data.get("trim_start", 0.0))
        self.trim_end.set(data.get("trim_end", 0.0))

    def on_close(self) -> None:
        _settings.save(self._collect_settings())
        self.root.destroy()

    def _restore_defaults(self) -> None:
        self._apply_settings(_settings.DEFAULTS)
        if self._font_map:
            names = list(self._font_map.keys())
            default = next((n for n in names if "Liberation Sans" in n and "Bold" in n), None)
            if default is None:
                default = next((n for n in names if "Sans" in n and "Bold" in n), names[0] if names else "")
            self.font_name.set(default)
            self._update_font_preview()

    # ------------------------------------------------------------------
    # Browse helpers
    # ------------------------------------------------------------------

    def _browse_bg(self) -> None:
        path = filedialog.askopenfilename(
            title="Select background",
            filetypes=[
                ("All supported", "*.gif *.mp4 *.mov *.webm *.jpg *.jpeg *.png *.bmp *.tiff *.tif *.webp"),
                ("GIF files", "*.gif"),
                ("Video files", "*.mp4 *.mov *.webm"),
                ("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.webp"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.bg_path.set(path)

    def _browse_audio(self) -> None:
        path = filedialog.askopenfilename(
            title="Select audio file",
            filetypes=[
                ("Audio files", "*.mp3 *.wav *.m4a *.aac *.flac *.ogg"),
                ("MP3 files", "*.mp3"),
                ("WAV files", "*.wav"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.audio_path.set(path)
            if self.output_path.get() in ("", "audiogram.mp4"):
                stem = Path(path).stem
                suggested = str(Path(path).parent / f"{stem}_audiogram.mp4")
                self.output_path.set(suggested)
            self.trim_enabled.set(False)
            self.trim_start.set(0.0)
            self.trim_end.set(0.0)
            self._audio_duration = 0.0

    def _browse_output(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save audiogram as",
            defaultextension=".mp4",
            filetypes=[("MP4 video", "*.mp4")],
        )
        if path:
            self.output_path.set(path)

    def _pick_text_color(self) -> None:
        result = colorchooser.askcolor(color=self.text_color, title="Choose text color")
        if result and result[1]:
            self.text_color = result[1]
            self._text_color_btn.config(bg=self.text_color)

    def _pick_highlight_color(self) -> None:
        result = colorchooser.askcolor(color=self.highlight_color, title="Choose highlight color")
        if result and result[1]:
            self.highlight_color = result[1]
            self._highlight_btn.config(bg=self.highlight_color)

    def _browse_wm_image(self) -> None:
        path = filedialog.askopenfilename(
            title="Select watermark image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.bmp *.webp"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.wm_image_path.set(path)

    def _pick_wm_color(self) -> None:
        result = colorchooser.askcolor(color=self.wm_color, title="Choose watermark color")
        if result and result[1]:
            self.wm_color = result[1]
            self._wm_color_btn.config(bg=self.wm_color)

    def _update_opacity_label(self, *_) -> None:
        self._wm_opacity_label.config(text=f"{int(self.wm_opacity.get())}%")

    def _on_resolution_changed(self, _event=None) -> None:
        _, suggested_font = _RESOLUTIONS.get(self.resolution.get(), (None, 40))
        self.font_size.set(suggested_font)

    def _open_waveform_settings(self) -> None:
        from gui.waveform_settings import WaveformSettingsDialog
        WaveformSettingsDialog(self.root, self)

    def _update_wf_status(self, *_) -> None:
        on = self.wf_enabled.get()
        self._wf_status_label.config(
            text="(on)" if on else "(off)",
            foreground="#2e7d32" if on else "#888888",
        )

    def _open_trim_dialog(self) -> None:
        from gui.trim_dialog import TrimDialog
        TrimDialog(self.root, self)

    def _update_trim_status(self, *_) -> None:
        from core.trim import format_timecode
        if self.trim_enabled.get():
            text = f"({format_timecode(self.trim_start.get())} – {format_timecode(self.trim_end.get())})"
            self._trim_status_label.config(text=text, foreground="#2e7d32")
        else:
            self._trim_status_label.config(text="(full)", foreground="#888888")

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def _generate(self) -> None:
        if self._running:
            return

        bg = self.bg_path.get().strip()
        audio = self.audio_path.get().strip()
        out = self.output_path.get().strip()

        if not bg:
            messagebox.showerror("Missing input", "Please select a background file.")
            return
        if not audio:
            messagebox.showerror("Missing input", "Please select an audio file.")
            return
        if not out:
            messagebox.showerror("Missing output", "Please specify an output file path.")
            return

        self._running = True
        self._cancel_event.clear()
        self._transcript_ready.clear()
        self._gen_btn.config(state=tk.DISABLED)
        self._cancel_btn.config(state=tk.NORMAL)
        self._progress_var.set(0)
        self._progress_bar.config(mode="indeterminate")
        self._progress_bar.start(12)

        threading.Thread(target=self._worker, args=(bg, audio, out), daemon=True).start()

    def _cancel(self) -> None:
        self._cancel_event.set()
        self._cancel_btn.config(state=tk.DISABLED)
        self._status_var.set("Cancelling…")

    def _build_waveform_config(self):
        from core.waveform import WaveformConfig

        style_map = {"Line": "line", "Rounded Bars": "bars", "Circular": "circular"}
        mode_map = {"Reactive": "reactive", "Progress": "progress"}

        placement = "tile" if self.wf_placement.get() == "Tile" else "stretch"
        pos = self.wf_position.get().strip().lower()
        if placement == "tile":
            region = "bottom"
            cell = pos.replace(" ", "-")          # "Top Right" -> "top-right"
        else:
            region = pos                          # "Top" / "Middle" / "Bottom"
            cell = "middle-center"

        return WaveformConfig(
            enabled=self.wf_enabled.get(),
            mode=mode_map.get(self.wf_mode.get(), "reactive"),
            style=style_map.get(self.wf_style.get(), "bars"),
            color=_hex_to_rgb(self.wf_color),
            gradient_color=_hex_to_rgb(self.wf_gradient_color) if self.wf_use_gradient.get() else None,
            opacity=self.wf_opacity.get() / 100.0,
            placement_mode=placement,
            region=region,
            cell=cell,
            sensitivity=float(self.wf_sensitivity.get()),
            smoothing=float(self.wf_smoothing.get()),
            mirror=self.wf_mirror.get(),
            bar_count=int(self.wf_bar_count.get()),
            thickness=int(self.wf_thickness.get()),
        )

    def _worker(self, bg_path: str, audio_path: str, output_path: str) -> None:
        try:
            from core.composer import compose_video
            from core.transcriber import transcribe

            def status(msg: str) -> None:
                self._queue.put(("status", msg))

            def video_progress(p: float) -> None:
                self._queue.put(("progress", 50 + p * 50))

            trim_start = self.trim_start.get() if self.trim_enabled.get() else None
            trim_end = self.trim_end.get() if self.trim_enabled.get() else None

            segments = transcribe(
                audio_path, model_size=self.model_size.get(),
                status_callback=status, trim_start=trim_start, trim_end=trim_end,
            )

            # Check for cancel between transcription and rendering
            if self._cancel_event.is_set():
                raise InterruptedError

            self._queue.put(("switch_determinate", 50))

            # Optional transcript review — block until user clicks Render or Cancel
            if self.review_transcript.get():
                self._edited_segments = segments
                self._queue.put(("show_transcript", segments))
                while True:
                    if self._cancel_event.wait(timeout=0.05):
                        raise InterruptedError
                    if self._transcript_ready.is_set():
                        break
                self._transcript_ready.clear()
                segments = self._edited_segments

            from core.watermark import WatermarkConfig
            target_size, _ = _RESOLUTIONS.get(self.resolution.get(), (None, 40))
            crf, preset = _QUALITIES.get(self.quality.get(), (18, "slow"))
            font_path = self._font_map.get(self.font_name.get(), "")

            _pos_map = {
                "Top Left": "top-left", "Top Right": "top-right",
                "Bottom Left": "bottom-left", "Bottom Right": "bottom-right",
            }
            wm_cfg = WatermarkConfig(
                text=self.wm_text.get().strip(),
                image_path=self.wm_image_path.get().strip(),
                position=_pos_map.get(self.wm_position.get(), "bottom-right"),
                opacity=self.wm_opacity.get() / 100.0,
                font_size=self.wm_font_size.get(),
                font_path=font_path,
                color=_hex_to_rgb(self.wm_color),
            )

            wf_cfg = self._build_waveform_config()

            compose_video(
                bg_path=bg_path,
                audio_path=audio_path,
                segments=segments,
                output_path=output_path,
                fps=self.fps.get(),
                font_size=self.font_size.get(),
                text_color=_hex_to_rgb(self.text_color),
                highlight_color=_hex_to_rgb(self.highlight_color),
                target_size=target_size,
                crf=crf,
                preset=preset,
                watermark_config=wm_cfg,
                waveform_config=wf_cfg,
                font_path=font_path,
                cancel_event=self._cancel_event,
                status_callback=status,
                progress_callback=video_progress,
                trim_start=trim_start,
                trim_end=trim_end,
            )
            self._queue.put(("done", output_path))

        except InterruptedError:
            self._queue.put(("cancelled", output_path))
        except Exception as exc:
            self._queue.put(("error", str(exc)))

    def _on_transcript_render(self, edited_segments) -> None:
        self._edited_segments = edited_segments
        self._transcript_ready.set()

    # ------------------------------------------------------------------
    # Queue polling (runs on main thread)
    # ------------------------------------------------------------------

    def _poll(self) -> None:
        try:
            while True:
                kind, value = self._queue.get_nowait()
                if kind == "status":
                    self._status_var.set(value)
                elif kind == "switch_determinate":
                    self._progress_bar.stop()
                    self._progress_bar.config(mode="determinate")
                    self._progress_var.set(float(value))
                elif kind == "progress":
                    self._progress_var.set(float(value))
                elif kind == "show_transcript":
                    from gui.transcript_editor import TranscriptEditorDialog
                    TranscriptEditorDialog(
                        self.root, value,
                        on_render=self._on_transcript_render,
                        on_cancel=self._cancel,
                    )
                elif kind == "done":
                    self._progress_var.set(100)
                    self._status_var.set(f"Done! Saved to: {value}")
                    self._reset_controls()
                    messagebox.showinfo("Done", f"Audiogram saved to:\n{value}")
                elif kind == "cancelled":
                    self._status_var.set("Cancelled")
                    self._progress_var.set(0)
                    self._reset_controls()
                    # Remove partial output and any moviepy temp audio file
                    Path(value).unlink(missing_ok=True)
                    stem = Path(value).stem
                    for tmp in Path(value).parent.glob(f"{stem}_TEMP_MPY_wvf_snd.*"):
                        tmp.unlink(missing_ok=True)
                elif kind == "error":
                    self._status_var.set(f"Error: {value}")
                    self._reset_controls()
                    messagebox.showerror("Error", value)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._poll)

    def _reset_controls(self) -> None:
        self._running = False
        self._progress_bar.stop()
        self._progress_bar.config(mode="determinate")
        self._gen_btn.config(state=tk.NORMAL)
        self._cancel_btn.config(state=tk.DISABLED)
