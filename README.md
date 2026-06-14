# Audiogrammer

Generate captioned audiogram videos from any audio file. Audiogrammer transcribes your audio with [OpenAI Whisper](https://github.com/openai/whisper), then renders an MP4 with animated word-by-word subtitle highlighting over your chosen background.

![Audiogrammer GUI](assets/screenshot.png)

## Features

- Word-by-word subtitle highlighting — current word highlighted, past words dimmed
- Background support: static image, animated GIF, or video (loops to match audio length)
- Aspect ratio presets: 16:9, 9:16 vertical, 1:1 square, or native source size
- Optional transcript review and edit before rendering
- Watermark: text and/or image overlay with configurable position and opacity
- Font selector pulling from system fonts, with a bundled fallback
- Cancel mid-render with automatic partial-file cleanup
- Runs fully offline — no API keys required

## Requirements

- **Python 3.12+**
- **FFmpeg** installed and available on your `PATH`
  - Linux: `sudo apt install ffmpeg`
  - macOS: `brew install ffmpeg`
  - Windows: download from [ffmpeg.org](https://ffmpeg.org/download.html)
- **tkinter** (Linux only — usually needs a separate install)
  - `sudo apt install python3-tk`
- ~2 GB free disk space for Whisper model files (downloaded automatically on first use to `~/.cache/whisper/`)

## Installation

```bash
git clone https://github.com/gjjeffers/audiogrammer.git
cd audiogrammer
pip install -r requirements.txt
python main.py
```

## Usage

1. **Input Files** — browse for a background file (image, GIF, or video) and an audio file
2. **Settings** — choose your Whisper model, resolution preset, quality, font, colors, and FPS
3. **Output** — pick where to save the resulting `.mp4`
4. **Watermark** *(optional)* — enter watermark text and/or an image path, then set its position and opacity
5. Click **Generate Audiogram** — the progress bar tracks transcription and then the render phase
6. *(Optional)* Check **"Review transcript before rendering"** to proofread and correct words before the render starts

## Supported Formats

| Type | Formats |
|---|---|
| Background | JPG, PNG, BMP, TIFF, WEBP, GIF, MP4, MOV, WEBM |
| Audio | MP3, WAV, M4A, AAC, FLAC, OGG |
| Output | MP4 (H.264 video + AAC audio) |

## Whisper Model Guide

Models are downloaded automatically on first use.

| Model | Approx. size | Speed | Notes |
|---|---|---|---|
| `tiny` | ~75 MB | Fastest | Good for quick tests |
| `base` | ~145 MB | Fast | Reasonable accuracy |
| `small` | ~465 MB | Moderate | Good balance |
| `medium` | ~1.5 GB | Slow | High accuracy |
| `large` | ~3 GB | Slowest | Best accuracy |

## Settings Reference

| Setting | Description |
|---|---|
| Whisper Model | Accuracy vs. speed trade-off for transcription |
| Review transcript | Opens an editor to fix transcription errors before rendering |
| Resolution | Output frame size; font size is auto-suggested per preset |
| Quality | Fast = CRF 28 / veryfast, Balanced = CRF 23 / medium, High = CRF 18 / slow |
| Font | System fonts discovered at startup; falls back to bundled Liberation Sans Bold |
| Font Size | Subtitle text size in pixels (16–160) |
| Video FPS | Output frame rate (12–60) |
| Text Color | Color for words not yet spoken |
| Highlight Color | Color for the currently spoken word |

## Tips

- **Social media verticals**: use the *Vertical 1080×1920 (9:16)* preset for Reels, Shorts, and TikTok
- **Podcasts**: *Square 1080×1080 (1:1)* works well across most platforms
- Use *High* quality for final exports and *Fast* for quick previews
- Cancelling during transcription takes effect after the Whisper pass completes — it cannot interrupt the model mid-run

## License

[Add your license here]
