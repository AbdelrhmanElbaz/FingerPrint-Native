# ui/main_window.py
# Phase 0: نافذة فارغة فقط — الهدف إثبات أن التطبيق يفتح كنافذة Native حقيقية.
# لا يوجد هنا أي منطق أعمال — هيُضاف تدريجيًا في المراحل التالية (راجع phases.md).

from PySide6.QtWidgets import QMainWindow, QLabel
from PySide6.QtCore import Qt

from app_config import APP_NAME, APP_VERSION, COLORS


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # RTL افتراضي لكل التطبيق (متطلب أساسي في claude.md)
        self.setLayoutDirection(Qt.RightToLeft)

        self.setWindowTitle(f"{APP_NAME} — v{APP_VERSION}")
        self.resize(1200, 800)

        # محتوى مؤقت لإثبات أن النافذة شغّالة فعليًا (سيُستبدل بـ QStackedWidget في Phase 3-4)
        placeholder = QLabel(
            f"✅ Phase 0: الهيكل الأساسي شغّال.\n"
            f"{APP_NAME} — الإصدار {APP_VERSION}\n\n"
            f"لو شايف الرسالة دي في نافذة حقيقية (مش متصفح) يبقى Phase 0 نجحت."
        )
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet(
            f"background: {COLORS['bg']}; color: {COLORS['text']}; "
            f"font-size: 16px; padding: 40px;"
        )
        self.setCentralWidget(placeholder)
