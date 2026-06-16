# audiogrammer.spec — PyInstaller build spec for Windows EXE
# Run: pyinstaller audiogrammer.spec

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_all

# Collect whisper model config/asset files bundled with the package
whisper_datas = collect_data_files("whisper")

# moviepy and imageio load their video/audio backends as plugins at runtime —
# collect_all grabs hiddenimports, datas, AND binaries in one pass, which
# collect_submodules alone won't catch.
moviepy_datas, moviepy_binaries, moviepy_hidden = collect_all('moviepy')
imageio_datas, imageio_binaries, imageio_hidden = collect_all('imageio')
imageio_ffmpeg_datas, imageio_ffmpeg_binaries, imageio_ffmpeg_hidden = collect_all('imageio_ffmpeg')

# Local packages — same dynamic-import situation as gui/core had
gui_hidden = collect_submodules('gui')
core_hidden = collect_submodules('core')
gui_datas = collect_data_files('gui')
core_datas = collect_data_files('core')

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[
        *moviepy_binaries,
        *imageio_binaries,
        *imageio_ffmpeg_binaries,
    ],
    datas=[
        ('assets/fonts/*.ttf', 'assets/fonts'),  # bundled fallback font
        *whisper_datas,
        *moviepy_datas,
        *imageio_datas,
        *imageio_ffmpeg_datas,
        *gui_datas,
        *core_datas,
    ],
    hiddenimports=[
        *collect_submodules('whisper'),
        *moviepy_hidden,
        *imageio_hidden,
        *imageio_ffmpeg_hidden,
        *gui_hidden,
        *core_hidden,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'pandas', 'scipy', 'PyQt5', 'PyQt6'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Audiogrammer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # keep True until everything's confirmed working
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)