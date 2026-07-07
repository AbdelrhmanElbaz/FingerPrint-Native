# packaging/build.spec
# PyInstaller spec — يبني exe واحد (onefile) للتطبيق.
# يُشغَّل بالأمر: pyinstaller packaging/build.spec --noconfirm
#
# ⚠️ لازم يضم ui/styles/theme.qss كـ data، وإلا الثيم العام (main.py →
# _load_theme) هيفشل بصمت جوه الـ exe المبني ويرجع الواجهة للستايل
# الافتراضي البدائي بتاع Qt.
#
# ⚠️ مشكلة شائعة جدًا مع PyInstaller --onefile: فشل استيراد numpy C-extensions
# ("Unable to find required dependencies: numpy") — بيحصل لأن PyInstaller
# التلقائي مش دايمًا بيلقط كل ملفات numpy/pandas الداخلية (DLLs + بيانات
# مساعدة). الحل: نستخدم collect_all لجمعهم بالكامل صراحة، ونستثنيهم من
# ضغط UPX (ضغط UPX معروف بإنه بيكسر DLLs بتاعة numpy/pandas أحيانًا).

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

block_cipher = None

PROJECT_ROOT = Path(SPECPATH).resolve().parent
THEME_QSS_PATH = PROJECT_ROOT / "ui" / "styles" / "theme.qss"

if not THEME_QSS_PATH.exists():
    raise FileNotFoundError(
        f"\n\n❌ ملف الثيم غير موجود: {THEME_QSS_PATH}\n"
        "تأكد إنك عملت commit/push لملف ui/styles/theme.qss قبل تشغيل البناء.\n"
    )

datas = [
    (str(THEME_QSS_PATH), "ui/styles"),
]
binaries = []
hiddenimports = ["PySide6.QtCharts"]

# ── تجميع كامل لكل مكتبة فيها C-extensions حساسة لـ PyInstaller ──────────
FULL_COLLECT_PACKAGES = ["numpy", "pandas", "openpyxl", "xlrd"]
for pkg in FULL_COLLECT_PACKAGES:
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

a = Analysis(
    [str(PROJECT_ROOT / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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

# أسماء DLLs بتاعة numpy/pandas بنستثنيها من ضغط UPX تحديدًا (upx=True لسه
# شغّال على باقي الملفات — بس مش على المكتبات دي).
UPX_EXCLUDE_PATTERNS = ["numpy", "pandas", "libopenblas", "vcomp", "mkl"]

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
    upx_exclude=UPX_EXCLUDE_PATTERNS,
    runtime_tmpdir=None,
    console=False,   # تطبيق واجهة رسومية — بدون نافذة Console سوداء خلفه
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,   # ضع مسار .ico هنا لاحقًا (Phase 9 — أيقونة نهائية)
)
