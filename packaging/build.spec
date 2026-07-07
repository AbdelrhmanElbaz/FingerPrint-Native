# packaging/build.spec
# Phase 0: تغليف أولي — بدون أيقونة حقيقية (Placeholder) وبدون أي أصول إضافية بعد.
# التشغيل: pyinstaller packaging/build.spec  (من داخل مجلد attendance_app)

# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['../main.py'],
    pathex=['..'],
    binaries=[],
    datas=[],
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
    name='AttendanceApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # بدون نافذة Console سوداء خلف التطبيق
    icon=None,           # Placeholder — سيُستبدل بأيقونة حقيقية لاحقًا (Phase 9)
    onefile=True,
)
