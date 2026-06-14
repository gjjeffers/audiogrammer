# Contributing to Audiogrammer

Thanks for your interest in contributing! Audiogrammer is an open-source desktop app for generating captioned audiogram videos, and contributions of all kinds are welcome — bug reports, feature ideas, documentation improvements, and code.

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold it. Please report unacceptable behavior to the maintainer.

## Ways to Contribute

- Report bugs by opening an issue using the Bug Report template.
- Request features or enhancements using the Feature Request template.
- Improve documentation, including this guide and the README.
- Submit code via a pull request.

## Development Setup

1. Fork the repository and clone your fork:

   ```bash
   git clone https://github.com/<your-username>/audiogrammer.git
   cd audiogrammer
   ```

2. Make sure you have the prerequisites installed:
   - Python 3.12 or newer
   - FFmpeg available on your PATH
   - tkinter (Linux: `sudo apt install python3-tk`)

3. (Recommended) Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # On Windows: .venv\\Scripts\\activate
   ```

4. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

5. Run the app:

   ```bash
   python main.py
   ```

## Making Changes

1. Create a topic branch off `main`:

   ```bash
   git checkout -b my-feature
   ```

2. Keep your changes focused — one logical change per pull request makes review easier.
3. Follow the existing code style and project structure (`core/` for rendering and transcription logic, `gui/` for the tkinter interface).
4. Test your changes locally by running the app and generating a sample audiogram before submitting.

## Commit Messages

- Write clear, descriptive commit messages in the imperative mood (e.g. "Add font preview", "Fix watermark during pauses").
- Reference related issues where relevant (e.g. "Fixes #12").

## Submitting a Pull Request

1. Push your branch to your fork and open a pull request against the `main` branch.
2. Fill out the pull request template, describing what changed and why.
3. Link any related issues.
4. Be responsive to review feedback — maintainers may request changes before merging.

## Reporting Bugs

When filing a bug, please include:

- A clear description of the problem and the expected behavior.
- Steps to reproduce.
- Your operating system, Python version, and FFmpeg version.
- Any relevant error output or screenshots.

## Questions

If you are unsure about anything, open an issue and ask. We are happy to help new contributors get started.

Thank you for helping make Audiogrammer better!
