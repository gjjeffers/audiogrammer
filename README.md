# Audiogrammer

Generate captioned audiogram videos from any audio file. Audiogrammer transcribes your audio with [OpenAI Whisper](https://github.com/openai/whisper), then renders an MP4 with animated word-by-word subtitle highlighting over your chosen background — with an optional reactive audio waveform overlay.

<img width="619" height="877" alt="image" src="https://github.com/user-attachments/assets/7986462b-1e6e-434b-b9ba-8d1b87c5dd3c" />


## Features

- Word-by-word subtitle highlighting — current word highlighted, past words dimmed
- Background support: static image, animated GIF, or video (loops to match audio length)
- Audio trimming — pick an in/out highlight window in a waveform scrubber; only that window is transcribed and rendered
- Audio waveform overlay — reactive spectrum or progress style, with bars / line / circular looks
- Aspect ratio presets: 16:9, 9:16 vertical, 1:1 square, or native source size
- Optional transcript review and edit before rendering
- Watermark: text and/or image overlay with configurable position and opacity
- Font selector pulling from system fonts, with a bundled fallback
- Settings auto-save on close and auto-load on startup, plus a one-click **Restore Defaults**
- Cancel mid-render with automatic partial-file cleanup
- Runs fully offline — no API keys required


## Setup

### Requirements

- **Python 3.12+**
- **FFmpeg** installed and available on your `PATH`
  - Linux: `sudo apt install ffmpeg`
  - macOS: `brew install ffmpeg`
  - Windows: download from [ffmpeg.org](https://ffmpeg.org/download.html)
- **tkinter** (Linux only — usually needs a separate install)
  - `sudo apt install python3-tk`
- ~2 GB free disk space for Whisper model files (downloaded automatically on first use to `~/.cache/whisper/`)

### Installation

```bash
git clone https://github.com/gjjeffers/audiogrammer.git
cd audiogrammer
pip install -r requirements.txt
```

Using a virtual environment is recommended:

```bash
python -m venv .venv
# Windows:        .venv\Scripts\activate
# macOS / Linux:  source .venv/bin/activate
pip install -r requirements.txt
```


## How to Run

From the project root:

```bash
python main.py
```

On launch the app checks that the required packages (`openai-whisper`, `moviepy`, `Pillow`, `numpy`) are installed and prints an install hint if anything is missing. The desktop window then opens.

Basic workflow:

1. **Input Files** — browse for a background file (image, GIF, or video) and an audio file. Picking an audio file auto-suggests an output name next to it.
2. **Settings** — choose the Whisper model, resolution, quality, font, colors, font size, and FPS.
3. *(Optional)* **Trim Audio…** — open the dialog to select a highlight window in the audio; only that window is transcribed and rendered. Leave unset to process the entire file.
4. *(Optional)* **Waveform Settings…** — open the dialog to enable and configure the audio waveform overlay.
5. **Output** — confirm or change where the `.mp4` is saved.
6. *(Optional)* **Watermark** — add text and/or an image overlay.
7. Click **Generate Audiogram** — the progress bar tracks transcription and then the render phase.
8. *(Optional)* Tick **Review transcript before rendering** to proofread and correct words before the render starts.

Your settings (including file paths and waveform options) are saved automatically when you close the window and restored the next time you open the app. Use **Restore Defaults** to reset everything.


## Breakdown of Features

### Input Files

| Control | Meaning |
|---|---|
| **Background** | The visual base of the video — a static image, an animated GIF, or a video clip. GIFs and videos loop to match the audio length. |
| **Audio File** | The audio to transcribe and use as the video soundtrack. |

### Settings

| Setting | Meaning |
|---|---|
| **Whisper Model** | Transcription model. Larger models are more accurate but slower (see the model guide below). |
| **Review transcript before rendering** | When checked, pauses after transcription and opens an editor so you can fix mis-heard words before the render starts. |
| **Resolution** | Output frame size. Choosing a preset also auto-suggests a matching font size. `Native (source size)` keeps the background's own dimensions. |
| **Quality** | Encoder trade-off between file size/speed and visual quality: `Fast` = CRF 28 / veryfast preset, `Balanced` = CRF 23 / medium, `High` = CRF 18 / slow. Lower CRF = higher quality, larger file. |
| **Font** | Caption typeface. The list is populated from system fonts discovered at startup; falls back to the bundled Liberation Sans Bold. A live preview shows the selected font. |
| **Font Size** | Subtitle text size in pixels (16–160). Auto-filled to a sensible value when you change the resolution preset, but you can override it. |
| **Video FPS** | Output frame rate (12–60). Higher is smoother but slower to render and larger on disk. |
| **Text Color** | Color of words that have not yet been spoken. |
| **Highlight Color** | Color of the word currently being spoken. |

### Trim Audio

Open the **Trim Audio…** dialog to select a highlight window instead of rendering the whole file. The status next to the button shows `(full)` or the chosen range.

| Control | Meaning |
|---|---|
| **Overview waveform** | The full file. Drag the two handles to set the coarse in/out points; the area outside the selection is dimmed. |
| **In / Out detail strips** | A zoomed view around each handle (±3s) for fine placement — drag inside a strip to nudge that handle precisely. |
| **In / Out fields** | Exact `m:ss.s` entry, each with ±0.1s / ±1s nudge buttons. Handles, detail strips, and fields stay in sync. |
| **Use Full Audio** | Clears the trim and renders the entire file. |

Trimming happens **before** transcription, so picking a 60-second window means Whisper only processes those 60 seconds — dramatically faster than transcribing a full episode. The selection resets when you choose a different audio file.

### Waveform Settings

Open via the **Waveform Settings…** button. The status next to the button shows `(on)` / `(off)`. The overlay draws an audio-driven visualization on top of the background.

| Setting | Meaning |
|---|---|
| **Enable waveform overlay** | Master on/off switch for the entire waveform feature. |
| **Mode** | `Reactive` animates per-frame from the audio's frequency spectrum (FFT). `Progress` draws a static waveform of the whole track with a playhead that fills as the audio plays. |
| **Style** | Shape of the visualization: `Line` (connected curve), `Rounded Bars` (vertical bars), or `Circular` (spokes radiating from a center ring). |
| **Color** | Primary color of the waveform. |
| **Gradient** | When enabled, the waveform blends from **Color** (low levels) to the chosen **gradient color** (high levels) instead of a solid fill. |
| **Placement** | `Stretch` spans the full width within a vertical band; `Tile` confines the waveform to one cell of a 3×3 grid. |
| **Position** | Where the waveform sits. With `Stretch`: Top / Middle / Bottom band. With `Tile`: a grid cell (e.g. Bottom Center, Top Right). |
| **Bar count** | Number of bars (or circular spokes / line points), 8–200. More bars = finer detail. |
| **Line width** | Stroke thickness in pixels (1–20), used by the Line and Circular styles. |
| **Opacity** | Overall transparency of the waveform layer, 0–100%. |
| **Sensitivity** | Gain multiplier applied to levels (0.2×–3.0×). Raise it to make quiet audio reach taller; levels are clipped at the top. |
| **Smoothing** | Temporal smoothing between frames (0–0.95) so motion looks less jittery. **Reactive mode only.** |
| **Mirror** | Draws a symmetric reflection of the waveform about the center of its band. |

### Output

| Control | Meaning |
|---|---|
| **Save to** | Path for the resulting `.mp4`. Auto-suggested as `<audioname>_audiogram.mp4` next to your audio file when you pick audio. |

### Watermark *(leave blank to disable)*

| Setting | Meaning |
|---|---|
| **Text** | Optional caption-independent text overlay (e.g. a handle or show name). Leave blank to skip. |
| **Color** | Color of the watermark text. |
| **Size** | Watermark text size in pixels (10–96). |
| **Image** | Optional image (e.g. a logo) overlaid on the video. Can be used alone or alongside text. |
| **Position** | Corner the watermark is anchored to: Top Left, Top Right, Bottom Left, or Bottom Right. |
| **Opacity** | Transparency of the watermark, 0–100%. |

### Generation Controls

| Control | Meaning |
|---|---|
| **Generate Audiogram** | Starts transcription and rendering. The progress bar runs indeterminate during transcription, then determinate (50–100%) during the render. |
| **Cancel** | Stops an in-progress job and cleans up the partial output file. Cancelling during transcription takes effect after the Whisper pass completes — it cannot interrupt the model mid-run. |
| **Restore Defaults** | Resets every setting (including waveform and watermark) back to its default value. |


## Supported Formats

| Type | Formats |
|---|---|
| Background | JPG, PNG, BMP, TIFF, WEBP, GIF, MP4, MOV, WEBM |
| Audio | MP3, WAV, M4A, AAC, FLAC, OGG |
| Watermark image | PNG, JPG, BMP, WEBP |
| Output | MP4 (H.264 video + AAC audio) |


## Whisper Model Guide

Models are downloaded automatically on first use.

| Model | Approx. size | Speed | Notes |
|---|---|---|---|
| `tiny` | ~75 MB | Fastest | Good for quick tests |
| `base` | ~145 MB | Fast | Reasonable accuracy (default) |
| `small` | ~465 MB | Moderate | Good balance |
| `medium` | ~1.5 GB | Slow | High accuracy |
| `large` | ~3 GB | Slowest | Best accuracy |


## Settings Persistence

Settings are stored as JSON at `~/.audiogrammer/settings.json`. They are written automatically when you close the window and loaded on startup. Delete that file (or click **Restore Defaults**) to start fresh.


## Tips

- **Social media verticals**: use the *Vertical 1080×1920 (9:16)* preset for Reels, Shorts, and TikTok
- **Podcasts**: *Square 1080×1080 (1:1)* works well across most platforms
- Use *High* quality for final exports and *Fast* for quick previews
- For a punchy reactive waveform, pair `Reactive` mode with `Rounded Bars`, a higher **Sensitivity**, and some **Smoothing** to keep motion clean
- Cancelling during transcription takes effect after the Whisper pass completes — it cannot interrupt the model mid-run


## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
