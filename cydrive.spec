# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for CyDrive — single-file console executable.
# Build with:  pyinstaller cydrive.spec
# Works on Windows, macOS, and Linux (run on each target OS).

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('cydrive/web_ui/static', 'cydrive/web_ui/static'),
        ('cydrive/web_ui/templates', 'cydrive/web_ui/templates'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CyDrive',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
