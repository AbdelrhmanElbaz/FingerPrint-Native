# packaging/build.spec
# PyInstaller spec — يبني exe واحد (onefile) للتطبيق.
# يُشغَّل بالأمر: pyinstaller packaging/build.spec --noconfirm
#
# ⚠️ لازم يضم ui/styles/theme.qss كـ data، وإلا الثيم العام (main.py →
# _load_theme) هيفشل بصمت جوه الـ exe المبني ويرجع الواجهة للستايل
# الافتراضي البدائي بتاع Qt.

import sys
from pathlib import Path

block_cipher = None

PROJECT_ROOT = Path(SPECPATH).resolve().parent

a = Analysis(
    [str(PROJECT_ROOT / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        (str(PROJECT_ROOT / "ui" / "styles" / "theme.qss"), "ui/styles"),
    ],
    hiddenimports=[],
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
    name="AttendanceApp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,   # تطبيق واجهة رسومية — بدون نافذة Console سوداء خلفه
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,   # ضع مسار .ico هنا لاحقًا (Phase 9 — أيقونة نهائية)
)
