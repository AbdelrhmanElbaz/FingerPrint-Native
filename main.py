# main.py
# نقطة الدخول الرئيسية للتطبيق.
# [تظبيط UI] تحميل ثيم عام (ui/styles/theme.qss) وتفعيل RTL على مستوى
# الـ Application كله (مش بس النافذة) — نظير claude.md §3 قاعدة 6.

import sys
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from db.database import init_db
from ui.main_window import MainWindow


def _resource_base_dir() -> Path:
    """
    مسار الموارد (theme.qss وغيرها) — يفرّق بين وضع التطوير العادي ووضع
    exe مبني بـ PyInstaller --onefile، لأن PyInstaller بيفك الملفات المرفقة
    (--add-data) في مجلد مؤقت (sys._MEIPASS) مش جنب الـ exe نفسه.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent


def _load_theme(app: QApplication):
    theme_path = _resource_base_dir() / "ui" / "styles" / "theme.qss"
    try:
        app.setStyleSheet(theme_path.read_text(encoding="utf-8"))
    except OSError:
        pass  # لو الملف مش موجود لأي سبب، يشتغل البرنامج بستايل Qt الافتراضي بدل ما يقفل


def main():
    init_db()  # ينشئ data/app.db وكل الجداول تلقائيًا لو أول تشغيل

    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft)
    _load_theme(app)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

