import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

# (target_size, suggested_font_size)
_RESOLUTIONS = {
    "Native (source size)": (None, 40),
    "720p  (1280×720)":     ((1280, 720), 52),
    "1080p (1920×1080)":    ((1920, 1080), 72),
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
        self.root.geometry("600x580")
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
        self.resolution = tk.StringVar(value="1080p (1920×1080)")  # must match a key in _RESOLUTIONS
        self.quality = tk.StringVar(value="High")
        self.text_color = "#FFFFFF"
        self.highlight_color = "#FFDC00"

        self._queue: queue.Queue = queue.Queue()
        self._running = False

        self._build_ui()
        self._poll()

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

        ttk.Label(settings, text="Resolution:").grid(row=1, column=0, sticky=tk.W, pady=4, padx=(0, 8))
        res_cb = ttk.Combobox(
            settings,
            textvariable=self.resolution,
            values=list(_RESOLUTIONS.keys()),
            width=20,
            state="readonly",
        )
        res_cb.grid(row=1, column=1, sticky=tk.W, pady=4)
        res_cb.bind("<<ComboboxSelected>>", self._on_resolution_changed)

        ttk.Label(settings, text="Quality:").grid(row=2, column=0, sticky=tk.W, pady=4, padx=(0, 8))
        ttk.Combobox(
            settings,
            textvariable=self.quality,
            values=list(_QUALITIES.keys()),
            width=14,
            state="readonly",
        ).grid(row=2, column=1, sticky=tk.W, pady=4)
        ttk.Label(settings, text="  (High = CRF 18, slow preset)").grid(row=2, column=2, sticky=tk.W)

        ttk.Label(settings, text="Font Size:").grid(row=3, column=0, sticky=tk.W, pady=4, padx=(0, 8))
        ttk.Spinbox(settings, textvariable=self.font_size, from_=16, to=160, width=6).grid(
            row=3, column=1, sticky=tk.W, pady=4
        )

        ttk.Label(settings, text="Video FPS:").grid(row=4, column=0, sticky=tk.W, pady=4, padx=(0, 8))
        ttk.Spinbox(settings, textvariable=self.fps, from_=12, to=60, width=6).grid(
            row=4, column=1, sticky=tk.W, pady=4
        )

        ttk.Label(settings, text="Text Color:").grid(row=5, column=0, sticky=tk.W, pady=4, padx=(0, 8))
        self._text_color_btn = tk.Button(
            settings,
            bg=self.text_color,
            width=5,
            relief=tk.GROOVE,
            command=self._pick_text_color,
        )
        self._text_color_btn.grid(row=5, column=1, sticky=tk.W, pady=4)

        ttk.Label(settings, text="Highlight Color:").grid(row=6, column=0, sticky=tk.W, pady=4, padx=(0, 8))
        self._highlight_btn = tk.Button(
            settings,
            bg=self.highlight_color,
            width=5,
            relief=tk.GROOVE,
            command=self._pick_highlight_color,
        )
        self._highlight_btn.grid(row=6, column=1, sticky=tk.W, pady=4)

        # ---- Output ------------------------------------------------------
        output = ttk.LabelFrame(root_frame, text="Output", padding=8)
        output.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(output, text="Save to:").grid(row=0, column=0, sticky=tk.W, padx=(0, 6), pady=4)
        ttk.Entry(output, textvariable=self.output_path).grid(row=0, column=1, sticky=tk.EW, padx=(0, 4), pady=4)
        ttk.Button(output, text="Browse…", command=self._browse_output).grid(row=0, column=2, pady=4)
        output.columnconfigure(1, weight=1)

        # ---- Generate button ---------------------------------------------
        self._gen_btn = ttk.Button(
            root_frame,
            text="Generate Audiogram",
            command=self._generate,
        )
        self._gen_btn.pack(pady=(4, 6))

        # ---- Progress area -----------------------------------------------
        progress_frame = ttk.Frame(root_frame)
        progress_frame.pack(fill=tk.X)

        self._progress_var = tk.DoubleVar(value=0)
        self._progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self._progress_var,
            maximum=100,
            mode="determinate",
        )
        self._progress_bar.pack(fill=tk.X, pady=(0, 4))

        self._status_var = tk.StringVar(value="Ready")
        ttk.Label(progress_frame, textvariable=self._status_var, anchor=tk.W).pack(fill=tk.X)

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

    def _on_resolution_changed(self, _event=None) -> None:
        _, suggested_font = _RESOLUTIONS.get(self.resolution.get(), (None, 40))
        self.font_size.set(suggested_font)

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
            messagebox.showerror("Missing input", "Please select a background file (GIF or MP4).")
            return
        if not audio:
            messagebox.showerror("Missing input", "Please select an audio file.")
            return
        if not out:
            messagebox.showerror("Missing output", "Please specify an output file path.")
            return

        self._running = True
        self._gen_btn.config(state=tk.DISABLED)
        self._progress_var.set(0)
        self._progress_bar.config(mode="indeterminate")
        self._progress_bar.start(12)

        thread = threading.Thread(
            target=self._worker,
            args=(bg, audio, out),
            daemon=True,
        )
        thread.start()

    def _worker(self, bg_path: str, audio_path: str, output_path: str) -> None:
        try:
            from core.composer import compose_video
            from core.transcriber import transcribe

            def status(msg: str) -> None:
                self._queue.put(("status", msg))

            def video_progress(p: float) -> None:
                # Map video progress (0-1) to 50-100% of the bar
                self._queue.put(("progress", 50 + p * 50))

            segments = transcribe(
                audio_path,
                model_size=self.model_size.get(),
                status_callback=status,
            )
            self._queue.put(("switch_determinate", 50))

            target_size, _ = _RESOLUTIONS.get(self.resolution.get(), (None, 40))
            crf, preset = _QUALITIES.get(self.quality.get(), (18, "slow"))

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
                status_callback=status,
                progress_callback=video_progress,
            )
            self._queue.put(("done", output_path))
        except Exception as exc:
            self._queue.put(("error", str(exc)))

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
                elif kind == "done":
                    self._progress_var.set(100)
                    self._status_var.set(f"Done! Saved to: {value}")
                    self._reset_controls()
                    messagebox.showinfo("Done", f"Audiogram saved to:\n{value}")
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
