# -*- mode: python ; coding: utf-8 -*-
# Build na macOS: python -m PyInstaller MusicBox_macos.spec --noconfirm
# Buduje .app NATYWNE (na M1 = arm64). Najprościej przez `MusicBox Build.command`.

from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('ui/theme.qss', 'ui'),
        ('assets', 'assets'),
        ('bin', 'bin'),
    ] + collect_data_files('ytmusicapi'),
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='MusicBox',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/icon.icns'],
)

app = BUNDLE(
    exe,
    name='MusicBox.app',
    icon='assets/icon.icns',
    bundle_identifier='org.musicbox.musicbox',
    version='0.6.0',
)
