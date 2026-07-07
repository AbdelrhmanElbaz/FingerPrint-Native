# ui/main_window.py
# Phase 4: ربط شجرة الملفات + الاستيراد بمحرك التحليل الفعلي (Parsers من
# Phase 2) وعرض النتائج في DashboardView حقيقية (KPI + جدول رواتب + رسوم).
#
# ⚠️ لا يوجد هنا أي تصحيح يدوي أو Day Override — هتُضاف في Phase 5.

from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QStackedWidget, QWidget, QVBoxLayout,
    QLabel, QPushButton, QStatusBar, QMessageBox
)
from PySide6.QtCore import Qt

from ui.widgets.file_tree_sidebar import FileTreeSidebar
from ui.widgets.import_dialog import ImportDialog
from ui.widgets.dashboard_view import DashboardView

from db.database import init_db, get_session
from db.repositories.company_repository import CompanyRepository
from db.repositories.attendance_repository import AttendanceFileRepository
from db.repositories.employee_repository import EmployeeRepository
from db.repositories.file_settings_repository import FileSettingsRepository
from db.repositories.employee_rate_repository import EmployeeRateRepository

from services.parsers.hikvision_parser import parse_file_hikvision
from services.parsers.zk_classic_parser import parse_file
from services.payroll_calculator import apply_early_tolerance, summarize_emp_days

from app_config import APP_NAME, APP_VERSION

ARABIC_MONTHS = [
    '', 'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
    'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'
]


class _DefaultFileSettings:
    """إعدادات افتراضية للوضع Anonymous — لا يوجد له سجل FileSettings في القاعدة."""
    cutoff_hour = 3.0
    saturate_minutes = None
    tolerance_enabled = False
    tolerance_minutes = 0
    duplicate_punch_tolerance = 10


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — v{APP_VERSION}")
        self.setLayoutDirection(Qt.RightToLeft)
        self.resize(1280, 800)

        init_db()
        self.session = get_session()
        self.company_repo = CompanyRepository(self.session)
        self.attendance_repo = AttendanceFileRepository(self.session)
        self.employee_repo = EmployeeRepository(self.session)
        self.file_settings_repo = FileSettingsRepository(self.session)
        self.rate_repo = EmployeeRateRepository(self.session)

        self._current_company_id = None
        self._current_company_name = None
        self._current_year = None
        self._current_month = None
        self._current_file_id = None
        self._current_emp_days = None
        self._eid_to_employee_id = {}   # external_code -> Employee.id (فارغ في وضع Anonymous)

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

        self.placeholder_page = QWidget()
        ph_layout = QVBoxLayout(self.placeholder_page)
        self.placeholder_label = QLabel("👆 ابدأ باستيراد ملف حضور من الشريط الجانبي")
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        ph_layout.addWidget(self.placeholder_label)

        import_btn = QPushButton("📤 استيراد ملف جديد")
        import_btn.clicked.connect(self.open_import_dialog)
        ph_layout.addWidget(import_btn, alignment=Qt.AlignCenter)

        self.stack.addWidget(self.placeholder_page)

        # ── الشاشة الرئيسية الحقيقية (Dashboard) — Phase 4 ──
        self.dashboard_page = DashboardView()
        self.dashboard_page.rate_changed.connect(self._on_rate_changed)
        self.dashboard_page.employee_selected.connect(self._on_employee_selected)
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
    # شريط الحالة (StatusBar)
    # ══════════════════════════════════════════════════════════════════
    def _build_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.pending_label = QLabel("")
        self.status_bar.addPermanentWidget(self.pending_label)

    def update_pending_status(self, count: int):
        """يُستدعى من Phase 5 لتحديث عدد التعديلات المعلَّقة."""
        if count > 0:
            self.pending_label.setText(f"⏳ {count} تعديل معلَّق بانتظار Apply")
        else:
            self.pending_label.setText("")

    # ══════════════════════════════════════════════════════════════════
    # الاستيراد
    # ══════════════════════════════════════════════════════════════════
    def open_import_dialog(self):
        dialog = ImportDialog(self.company_repo, self.attendance_repo, parent=self)
        dialog.import_completed.connect(self._on_import_completed)
        dialog.exec()

    def _on_import_completed(self, payload: dict):
        if payload["is_anonymous"]:
            self._current_company_id = None
            self._current_company_name = None
            self._current_year = None
            self._current_month = None
            self._current_file_id = None
            self.setWindowTitle(f"{APP_NAME} — مراجعة مؤقتة (Anonymous)")

            self._run_analysis(
                file_bytes=payload["file_bytes"],
                file_format=payload["file_format"],
                company_id=None,
                settings=_DefaultFileSettings(),
                header_text="📤 مراجعة مؤقتة (Anonymous)",
            )
        else:
            self._current_company_id = payload["company_id"]
            self._current_company_name = payload["company_name"]
            self._current_year = payload["year"]
            self._current_month = payload["month"]
            self._current_file_id = payload["attendance_file_id"]

            self.sidebar.set_current_open(
                payload["company_id"], payload["year"], payload["month"]
            )
            self.setWindowTitle(
                f"{APP_NAME} — {payload['company_name']} "
                f"({payload['month']:02d}/{payload['year']})"
            )

            settings = self.file_settings_repo.get_or_create(self._current_file_id)
            self._run_analysis(
                file_bytes=payload["file_bytes"],
                file_format=payload["file_format"],
                company_id=self._current_company_id,
                settings=settings,
                header_text=f"📂 {payload['company_name']} — "
                            f"{ARABIC_MONTHS[payload['month']]} {payload['year']}",
            )

    # ══════════════════════════════════════════════════════════════════
    # فتح شهر من الشجرة
    # ══════════════════════════════════════════════════════════════════
    def _on_month_opened(self, company_id: int, company_name: str, year: int, month: int):
        att_file = self.attendance_repo.get_by_company_year_month(company_id, year, month)
        if not att_file:
            QMessageBox.critical(self, "خطأ", "تعذّر العثور على الملف في قاعدة البيانات.")
            return

        work_path = Path(att_file.working_file_path)
        if not work_path.exists():
            QMessageBox.critical(
                self, "خطأ",
                f"ملف العمل غير موجود على القرص:\n{work_path}\n"
                "قد يكون تم نقله أو حذفه يدويًا خارج البرنامج."
            )
            return

        file_bytes = work_path.read_bytes()

        self._current_company_id = company_id
        self._current_company_name = company_name
        self._current_year = year
        self._current_month = month
        self._current_file_id = att_file.id

        self.setWindowTitle(f"{APP_NAME} — {company_name} ({month:02d}/{year})")

        settings = self.file_settings_repo.get_or_create(att_file.id)
        self._run_analysis(
            file_bytes=file_bytes,
            file_format=att_file.file_format,
            company_id=company_id,
            settings=settings,
            header_text=f"📂 {company_name} — {ARABIC_MONTHS[month]} {year}",
        )

    # ══════════════════════════════════════════════════════════════════
    # نقطة الدمج المركزية: تحليل → تسامح → مزامنة موظفين → أسعار → عرض
    # ══════════════════════════════════════════════════════════════════
    def _run_analysis(self, file_bytes: bytes, file_format: str, company_id, settings, header_text: str):
        try:
            if file_format == "hikvision":
                df, emp_days = parse_file_hikvision(
                    file_bytes,
                    cutoff_hour=settings.cutoff_hour,
                    saturate_min=settings.saturate_minutes,
                    duplicate_punch_tolerance=settings.duplicate_punch_tolerance,
                )
            else:
                df, emp_days = parse_file(
                    file_bytes,
                    cutoff_hour=settings.cutoff_hour,
                    saturate_min=settings.saturate_minutes,
                    duplicate_punch_tolerance=settings.duplicate_punch_tolerance,
                )
        except Exception as e:
            QMessageBox.critical(
                self, "خطأ في تحليل الملف",
                f"تعذّر تحليل الملف بصيغة {file_format}:\n{e}\n\n"
                "تأكد أن الملف يطابق نوع الجهاز المختار عند الاستيراد."
            )
            self._show_import_placeholder()
            return

        emp_days = apply_early_tolerance(
            emp_days,
            tolerance_minutes=settings.tolerance_minutes,
            tolerance_enabled=settings.tolerance_enabled,
            saturate_min=settings.saturate_minutes,
        )
        overrides_summary = summarize_emp_days(emp_days)
        self._current_emp_days = emp_days

        # ── مزامنة الموظفين مع القاعدة + تحميل أسعار الساعة المحفوظة ──
        hourly_rates = {}
        self._eid_to_employee_id = {}

        if company_id is not None:
            for _, row in df.iterrows():
                eid = str(row['id'])
                employee = self.employee_repo.get_or_create(
                    company_id=company_id,
                    external_code=eid,
                    name=row.get('name', ''),
                    department=row.get('department', ''),
                )
                self._eid_to_employee_id[eid] = employee.id

            rates_by_employee_id = self.rate_repo.get_rates_map_by_employee_id(company_id)
            for eid, emp_id in self._eid_to_employee_id.items():
                if emp_id in rates_by_employee_id:
                    hourly_rates[eid] = rates_by_employee_id[emp_id]

        self.dashboard_page.load_data(header_text, df, overrides_summary, hourly_rates)
        self.stack.setCurrentWidget(self.dashboard_page)

    # ══════════════════════════════════════════════════════════════════
    def _on_rate_changed(self, eid: str, rate: float):
        """حفظ سعر الساعة كإعداد افتراضي دائم للموظف داخل شركته (لو مش Anonymous)."""
        if self._current_company_id is None:
            return  # وضع Anonymous — السعر في الذاكرة فقط، بدون حفظ دائم
        employee_id = self._eid_to_employee_id.get(eid)
        if employee_id is None:
            return
        self.rate_repo.set_rate(self._current_company_id, employee_id, rate)

    # ══════════════════════════════════════════════════════════════════
    def _on_employee_selected(self, eid: str):
        """Phase 5: فتح EmployeeDetailView الكاملة. حاليًا Placeholder بسيط."""
        QMessageBox.information(
            self, "قريبًا",
            f"شاشة تفاصيل الموظف (ID: {eid}) هتُضاف في Phase 5 "
            "(التصحيحات اليدوية وReview Panel)."
        )

    # ══════════════════════════════════════════════════════════════════
    def _on_company_renamed(self, company_id: int, new_name: str):
        if company_id == self._current_company_id:
            self._current_company_name = new_name
            self.setWindowTitle(
                f"{APP_NAME} — {new_name} "
                f"({self._current_month:02d}/{self._current_year})"
            )

    def _on_tree_changed(self):
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
