# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for building a single-binary CodexA distribution."""

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['semantic_code_intelligence/cli/main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('semantic_code_intelligence', 'semantic_code_intelligence'),
    ],
    hiddenimports=[
        'click',
        'rich',
        'pydantic',
        'semantic_code_intelligence.cli.router',
        'semantic_code_intelligence.cli.main',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='codexa',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
