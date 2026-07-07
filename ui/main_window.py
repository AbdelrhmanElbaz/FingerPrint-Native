# ui/main_window.py
# النافذة الرئيسية — Phase 3: ربط شجرة الملفات (Sidebar) + نافذة الاستيراد.
#
# ⚠️ ملاحظات مهمة قبل التشغيل:
# 1. هذا الملف يفترض أنك عندك بالفعل CompanyRepository و AttendanceFileRepository
#    داخل db/repositories/ (من Phase 1). عدّل الـ import أدناه لو أسماء الملفات
#    أو الكلاسات مختلفة عندك.
# 2. الشاشات الحقيقية (Dashboard, Employee Detail) لسه هتتضاف في Phase 4/5 —
#    حالياً فيه Placeholder بسيط بدالها.

from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QStackedWidget, QWidget, QVBoxLayout,
    QLabel, QPushButton, QStatusBar, QMessageBox
)
from PySide6.QtCore import Qt

from ui.widgets.file_tree_sidebar import FileTreeSidebar
from ui.widgets.import_dialog import ImportDialog

from db.database import init_db, get_session
from db.repositories.company_repository import CompanyRepository
from db.repositories.attendance_repository import AttendanceFileRepository

from app_config import APP_NAME, APP_VERSION


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — v{APP_VERSION}")
        self.setLayoutDirection(Qt.RightToLeft)
        self.resize(1280, 800)

        # ── إعداد الـ Repositories (نمرر جلسة قاعدة البيانات) ──
        init_db()  # يضمن وجود الجداول لو أول مرة تفتح فيها هذه النافذة بمعزل عن main.py
        self.session = get_session()
        self.company_repo = CompanyRepository(self.session)
        self.attendance_repo = AttendanceFileRepository(self.session)

        self._current_company_id = None
        self._current_company_name = None
        self._current_year = None
        self._current_month = None

        self._build_central_stack()
        self._build_sidebar()
        self._build_status_bar()

        self._show_import_placeholder()

    # ══════════════════════════════════════════════════════════════════
    # المحتوى المركزي (QStackedWidget)
    # ══════════════════════════════════════════════════════════════════
    def _build_central_stack(self):
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # ── شاشة placeholder لحد ما نضيف Dashboard الحقيقي في Phase 4 ──
        self.placeholder_page = QWidget()
        ph_layout = QVBoxLayout(self.placeholder_page)
        self.placeholder_label = QLabel("👆 ابدأ باستيراد ملف حضور من الشريط الجانبي")
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        ph_layout.addWidget(self.placeholder_label)

        import_btn = QPushButton("📤 استيراد ملف جديد")
        import_btn.clicked.connect(self.open_import_dialog)
        ph_layout.addWidget(import_btn, alignment=Qt.AlignCenter)

        self.stack.addWidget(self.placeholder_page)

        # ── مكان الشاشة الرئيسية الحقيقية (Dashboard) — تُضاف لاحقًا Phase 4 ──
        self.dashboard_page = QWidget()
        dash_layout = QVBoxLayout(self.dashboard_page)
        self.dashboard_title = QLabel("")
        self.dashboard_title.setAlignment(Qt.AlignCenter)
        dash_layout.addWidget(self.dashboard_title)
        dash_layout.addWidget(QLabel("📊 لوحة التحكم والرواتب ستُضاف هنا في Phase 4"))
        self.stack.addWidget(self.dashboard_page)

    def _show_import_placeholder(self):
        self.stack.setCurrentWidget(self.placeholder_page)
        self.setWindowTitle(f"{APP_NAME} — v{APP_VERSION}")

    # ══════════════════════════════════════════════════════════════════
    # الشريط الجانبي (Sidebar / Dock Widget)
    # ══════════════════════════════════════════════════════════════════
    def _build_sidebar(self):
        self.sidebar = FileTreeSidebar(self.company_repo, self.attendance_repo)
        self.sidebar.month_opened.connect(self._on_month_opened)
        self.sidebar.company_renamed.connect(self._on_company_renamed)
        self.sidebar.tree_changed.connect(self._on_tree_changed)

        dock = QDockWidget("📁 ملفاتي", self)
        dock.setWidget(self.sidebar)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self.sidebar_dock = dock

    # ══════════════════════════════════════════════════════════════════
    # شريط الحالة (StatusBar) — بديل الـ Floating Apply Bar
    # ══════════════════════════════════════════════════════════════════
    def _build_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.pending_label = QLabel("")
        self.status_bar.addPermanentWidget(self.pending_label)

    def update_pending_status(self, count: int):
        """يُستدعى من شاشات لاحقة (Phase 5) لتحديث عدد التعديلات المعلَّقة."""
        if count > 0:
            self.pending_label.setText(f"⏳ {count} تعديل معلَّق بانتظار Apply")
        else:
            self.pending_label.setText("")

    # ══════════════════════════════════════════════════════════════════
    # فتح نافذة الاستيراد
    # ══════════════════════════════════════════════════════════════════
    def open_import_dialog(self):
        dialog = ImportDialog(self.company_repo, self.attendance_repo, parent=self)
        dialog.import_completed.connect(self._on_import_completed)
        dialog.exec()

    def _on_import_completed(self, payload: dict):
        """
        يُستدعى بعد نجاح الاستيراد (Anonymous أو دائم).
        هنا المفروض تحليل الملف الفعلي (parsers) وتخزين النتائج —
        سيُنفَّذ بالتفصيل عند دمج Phase 4 (Dashboard) لأنه يحتاج
        استدعاء parse_file / parse_file_hikvision وربطها بالعرض.
        """
        if payload["is_anonymous"]:
            self._current_company_id = None
            self._current_company_name = None
            self._current_year = None
            self._current_month = None
            self.setWindowTitle("نظام الحضور والرواتب — مراجعة مؤقتة (Anonymous)")
        else:
            self._current_company_id = payload["company_id"]
            self._current_company_name = payload["company_name"]
            self._current_year = payload["year"]
            self._current_month = payload["month"]
            self.sidebar.set_current_open(
                payload["company_id"], payload["year"], payload["month"]
            )
            self.setWindowTitle(
                f"نظام الحضور والرواتب — {payload['company_name']} "
                f"({payload['month']:02d}/{payload['year']})"
            )

        # TODO (Phase 4): تمرير payload['file_bytes'] و payload['file_format']
        # لخدمة التحليل المناسبة (parse_file / parse_file_hikvision) وعرض
        # النتائج في self.dashboard_page، ثم:
        self.dashboard_title.setText(
            f"📂 {payload.get('company_name') or 'مراجعة مؤقتة'} "
            f"— {payload.get('month', '')}/{payload.get('year', '')}"
        )
        self.stack.setCurrentWidget(self.dashboard_page)

    # ══════════════════════════════════════════════════════════════════
    # فتح شهر من الشجرة
    # ══════════════════════════════════════════════════════════════════
    def _on_month_opened(self, company_id: int, company_name: str, year: int, month: int):
        # TODO (Phase 4): تحميل working_file من AttendanceFileRepository،
        # ثم تشغيل التحليل وعرض النتائج بدل الأسطر التالية فقط.
        self._current_company_id = company_id
        self._current_company_name = company_name
        self._current_year = year
        self._current_month = month

        self.setWindowTitle(f"نظام الحضور والرواتب — {company_name} ({month:02d}/{year})")
        self.dashboard_title.setText(f"📂 {company_name} — {month}/{year}")
        self.stack.setCurrentWidget(self.dashboard_page)

    # ══════════════════════════════════════════════════════════════════
    def _on_company_renamed(self, company_id: int, new_name: str):
        if company_id == self._current_company_id:
            self._current_company_name = new_name
            self.setWindowTitle(
                f"نظام الحضور والرواتب — {new_name} "
                f"({self._current_month:02d}/{self._current_year})"
            )

    def _on_tree_changed(self):
        # لو الملف المفتوح حاليًا اتحذف، نرجع للـ placeholder
        if self._current_company_id is None and self.stack.currentWidget() is self.dashboard_page:
            self._show_import_placeholder()

    # ══════════════════════════════════════════════════════════════════
    def closeEvent(self, event):
        # TODO (Phase 5+): فحص وجود تعديلات معلّقة قبل الإغلاق وعرض تأكيد.
        try:
            self.session.close()
        except Exception:
            pass
        event.accept()
