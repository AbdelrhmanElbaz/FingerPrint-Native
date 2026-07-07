# main.py
# نقطة الدخول الرئيسية للتطبيق.
# Phase 0: تشغيل نافذة فارغة فقط للتأكد من أن كل السلسلة (بيئة Python → PySide6 → exe) شغّالة.

import sys
from PySide6.QtWidgets import QApplication

from db.database import init_db
from ui.main_window import MainWindow


def main():
    init_db()  # ينشئ data/app.db وكل الجداول تلقائيًا لو أول تشغيل

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
