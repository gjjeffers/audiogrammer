# audiogrammer.spec — PyInstaller build spec for Windows EXE
# Run: pyinstaller audiogrammer.spec

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect whisper model config/asset files bundled with the package
whisper_datas = collect_data_files("whisper")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets/fonts/*.ttf', 'assets/fonts'),  # bundled fallback font
        *whisper_datas,                           # whisper assets (mel filters, etc.)
    ],
    hiddenimports=collect_submodules('whisper'),
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
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,   # no terminal window — GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,        # add an .ico file path here when you have one
)
