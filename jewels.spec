
# PyInstaller spec for Jewels
# Build on Windows: pyinstaller jewels.spec
block_cipher = None

from PyInstaller.utils.hooks import collect_data_files
import cv2

opencv_data = [(cv2.data.haarcascades, "cv2/data/haarcascades")]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=opencv_data,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch','transformers','rembg'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='jewels',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='jewels'
)
