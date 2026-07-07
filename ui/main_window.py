# ui/main_window.py
# Phase 8: دمج SettingsPanel (Cutoff / Saturate / Tolerance / Duplicate Punch)
# كـ QDockWidget مستقل، مع إعادة تحليل تلقائية عند أي تغيير إعداد.
# التغييرات عن نسخة Phase 5 مُعلَّمة بتعليقات "# [Phase 8]".

from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QStackedWidget, QWidget, QVBoxLayout,
    QLabel, QPushButton, QStatusBar, QMessageBox
)
from PySide6.QtCore import Qt

from ui.widgets.file_tree_sidebar import FileTreeSidebar
from ui.widgets.import_dialog import ImportDialog
from ui.widgets.dashboard_view import DashboardView
from ui.widgets.employee_detail_view import EmployeeDetailView
from ui.widgets.settings_panel import SettingsPanel   # [Phase 8]

from db.database import init_db, get_session
from db.repositories.company_repository import CompanyRepository
from db.repositories.attendance_repository import AttendanceFileRepository
from db.repositories.employee_repository import EmployeeRepository
from db.repositories.file_settings_repository import FileSettingsRepository
from db.repositories.employee_rate_repository import EmployeeRateRepository
from db.repositories.correction_state_repository import CorrectionStateRepository

from services.parsers.hikvision_parser import parse_file_hikvision
from services.parsers.zk_classic_parser import parse_file
from services.payroll_calculator import apply_early_tolerance, summarize_emp_days
from services.corrections_engine import apply_overrides, bulk_smart_apply_all
from ui.widgets.bulk_smart_apply_dialog import BulkSmartApplyDialog

from app_config import APP_NAME, APP_VERSION

ARABIC_MONTHS = [
    '', 'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
    'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'
]


class _DefaultFileSettings:
    """إعدادات افتراضية للوضع Anonymous — لا يوجد له سجل FileSettings في القاعدة.

    [Phase 8] أصبحت instance-level بدل class-level فقط، عشان SettingsPanel
    يقدر يعدّلها Runtime (عبر _run_analysis المُعاد استدعاؤه) بدون أي تأثير
    على أي وضع Anonymous آخر مفتوح لاحقًا في نفس الجلسة.
    """
    def __init__(self):
        self.cutoff_hour = 3.0
        self.saturate_minutes = None
        self.tolerance_enabled = False
        self.tolerance_minutes = 0
        self.duplicate_punch_tolerance = 10


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
        self.correction_state_repo = CorrectionStateRepository(self.session)

        self._current_company_id = None
        self._current_company_name = None
        self._current_year = None
        self._current_month = None
        self._current_file_id = None
        self._current_emp_days = None
        self._current_df = None
        self._eid_to_employee_id = {}
        self._eid_to_name = {}

        self._current_corrections = {}
        self._current_day_overrides = {}

        # [Phase 8] لازم نخزّن bytes الملف الحالي وصيغته عشان نقدر نعيد
        # التحليل من الصفر لما إعداد يتغيّر (Cutoff/Saturate/Tolerance...)
        # بدون الحاجة لإعادة قراءته من القرص أو من ImportDialog كل مرة.
        self._current_file_bytes = None
        self._current_file_format = None
        self._current_header_text = ""
        # [Phase 8] الإعدادات الحالية (FileSettings من القاعدة، أو
        # _DefaultFileSettings في وضع Anonymous) — نحتفظ بها هنا عشان
        # _on_settings_changed يقدر يحدّثها Runtime في وضع Anonymous
        # (لأنه مفيش صف FileSettings بالقاعدة يتحدّث بدله).
        self._current_settings = None

        self._build_central_stack()
        self._build_sidebar()
        self._build_settings_dock()   # [Phase 8]
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

        # ── الشاشة الرئيسية (Dashboard) ──
        self.dashboard_page = DashboardView()
        self.dashboard_page.rate_changed.connect(self._on_rate_changed)
        self.dashboard_page.employee_selected.connect(self._on_employee_selected)
        self.dashboard_page.import_new_requested.connect(self.open_import_dialog)
        self.dashboard_page.reset_to_original_requested.connect(self._on_reset_all_clicked)
        self.dashboard_page.bulk_smart_apply_requested.connect(self._on_bulk_smart_apply_all_clicked)
        self.stack.addWidget(self.dashboard_page)

        # ── شاشة تفاصيل الموظف ──
        self.employee_detail_page = EmployeeDetailView()
        self.employee_detail_page.back_requested.connect(self._on_employee_detail_back)
        self.employee_detail_page.changes_saved.connect(self._on_employee_changes_saved)
        self.employee_detail_page.reset_requested.connect(self._on_employee_reset)
        self.employee_detail_page.pending_count_changed.connect(self.update_pending_status)
        self.stack.addWidget(self.employee_detail_page)

    def _show_import_placeholder(self):
        self.stack.setCurrentWidget(self.placeholder_page)
        self.setWindowTitle(f"{APP_NAME} — v{APP_VERSION}")
        # [Phase 8] تعطيل لوحة الإعدادات ومسح حالة الملف الحالي بالكامل
        self.settings_panel.clear()
        self._current_file_bytes = None
        self._current_file_format = None
        self._current_settings = None

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
    # [Phase 8] لوحة الإعدادات (Dock مستقل — شقيق لشجرة الملفات)
    # ══════════════════════════════════════════════════════════════════
    def _build_settings_dock(self):
        self.settings_panel = SettingsPanel()
        self.settings_panel.settings_changed.connect(self._on_settings_changed)

        dock = QDockWidget("⚙️ إعدادات الشيفتات", self)
        dock.setWidget(self.settings_panel)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        # الشجرة يمين (RTL) — الإعدادات تُوضع يسار عشان متتزاحمش مع بعض.
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
        self.settings_dock = dock

    # ══════════════════════════════════════════════════════════════════
    # شريط الحالة (StatusBar)
    # ══════════════════════════════════════════════════════════════════
    def _build_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.pending_label = QLabel("")
        self.status_bar.addPermanentWidget(self.pending_label)

    def update_pending_status(self, count: int):
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
            self._current_corrections = {}
            self._current_day_overrides = {}
            self.setWindowTitle(f"{APP_NAME} — مراجعة مؤقتة (Anonymous)")

            # [Phase 8] تخزين bytes/format/header + إعدادات افتراضية قابلة للتعديل Runtime
            self._current_file_bytes = payload["file_bytes"]
            self._current_file_format = payload["file_format"]
            self._current_header_text = "📤 مراجعة مؤقتة (Anonymous)"
            self._current_settings = _DefaultFileSettings()

            self._run_analysis(
                file_bytes=self._current_file_bytes,
                file_format=self._current_file_format,
                company_id=None,
                settings=self._current_settings,
                header_text=self._current_header_text,
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

            state = self.correction_state_repo.load(self._current_file_id)
            self._current_corrections = state['corrections']
            self._current_day_overrides = state['day_overrides']

            # [Phase 8]
            self._current_file_bytes = payload["file_bytes"]
            self._current_file_format = payload["file_format"]
            self._current_header_text = (
                f"📂 {payload['company_name']} — "
                f"{ARABIC_MONTHS[payload['month']]} {payload['year']}"
            )
            self._current_settings = self.file_settings_repo.get_or_create(self._current_file_id)

            self._run_analysis(
                file_bytes=self._current_file_bytes,
                file_format=self._current_file_format,
                company_id=self._current_company_id,
                settings=self._current_settings,
                header_text=self._current_header_text,
            )

    # ══════════════════════════════════════════════════════════════════
    # 🔄 العودة للأصل — استعادة الملف كاملًا (كل الموظفين) لحالته الأصلية
    # نظير الزر المكافئ في oldapp.py (سطر 4443/4457) — بخلاف "🔄 استعادة
    # الافتراضي" في EmployeeDetailView اللي بيمسح موظف واحد بس.
    # ══════════════════════════════════════════════════════════════════
    def _on_reset_all_clicked(self):
        if self._current_file_id is None:
            QMessageBox.information(
                self, "غير متاح",
                "زر 'العودة للأصل' متاح فقط للملفات المحفوظة (غير المؤقتة/Anonymous)."
            )
            return

        confirm = QMessageBox.warning(
            self, "⚠️ تأكيد العودة للأصل",
            "سيتم حذف جميع التعديلات والتصحيحات لكل الموظفين في هذا الملف "
            f"({self._current_header_text}) والعودة للملف الأصلي كما تم استيراده أول مرة.\n\n"
            "هذا الإجراء لا يمكن التراجع عنه.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        att_file = self.attendance_repo.get_by_id(self._current_file_id)
        if not att_file or not att_file.original_file_path:
            QMessageBox.critical(self, "خطأ", "تعذّر العثور على النسخة الأصلية لهذا الملف.")
            return

        original_path = Path(att_file.original_file_path)
        if not original_path.exists():
            QMessageBox.critical(
                self, "خطأ",
                f"ملف النسخة الأصلية غير موجود على القرص:\n{original_path}"
            )
            return

        original_bytes = original_path.read_bytes()

        # إعادة كتابة ملف العمل بنفس محتوى الأصل — نظير
        # save_work_file(_orig, _co, _yr, _mo) في oldapp.py.
        working_path = Path(att_file.working_file_path)
        working_path.write_bytes(original_bytes)

        # مسح كل التصحيحات والـ day_overrides الخاصة بهذا الملف — لكل الموظفين
        # دفعة واحدة (مش موظف واحد بس زي _on_employee_reset).
        self._current_corrections = {}
        self._current_day_overrides = {}
        self.correction_state_repo.save(self._current_file_id, {}, {})

        # ── ملاحظة تصميم مقصودة (تختلف عن oldapp.py) ──
        # في oldapp.py كانت أسعار الساعة (saved_rates) مخزّنة *لكل ملف شهر*
        # فتُمسح مع "العودة للأصل". في النسخة الـ Native الحالية الأسعار
        # مخزّنة على مستوى الشركة كلها (employee_rate_defaults — schema.md)
        # عشان تفضل ثابتة من شهر للتاني. لذلك هذا الزر عمدًا **لا يمسح**
        # أسعار الساعة — مسحها كان هيأثر على كل شهور الشركة مش بس هذا الملف.
        # لو الاتفاق مع العميل يتطلب مسح الأسعار كمان، ده قرار منتج محتاج
        # تأكيد صريح لأنه تغيير سلوك عن الأصل.

        self._current_file_bytes = original_bytes
        self._run_analysis(
            file_bytes=self._current_file_bytes,
            file_format=self._current_file_format,
            company_id=self._current_company_id,
            settings=self._current_settings,
            header_text=self._current_header_text,
        )
        QMessageBox.information(self, "تم", "✅ تم استعادة الملف الأصلي بنجاح لكل الموظفين.")

    # ══════════════════════════════════════════════════════════════════
    # 🤖 Bulk Smart Apply لكل الموظفين (الشاشة الرئيسية)
    # نظير bulk_smart_apply_all + apply_all_pending في oldapp.py (سطر 4671
    # و4757) — بخلاف "🤖 Bulk Smart Apply" الموجود جوه EmployeeDetailView
    # اللي بيشتغل لموظف واحد بس. هنا بيشتغل على self._current_emp_days
    # كامل (كل الموظفين) ويطبّق مباشرة (مش عبر PendingChangesStore محلي).
    # ══════════════════════════════════════════════════════════════════
    def _on_bulk_smart_apply_all_clicked(self, min_sample: int):
        if self._current_emp_days is None:
            return

        result = bulk_smart_apply_all(
            self._current_emp_days,
            self._current_corrections,
            {},   # مفيش pending محلي على مستوى الشاشة الرئيسية — كل حاجة تُطبَّق مباشرة
            self._current_day_overrides,
            min_sample=min_sample,
        )

        dialog = BulkSmartApplyDialog(result['applied'], result['skipped'], parent=self)
        if not (dialog.exec() and result['applied']):
            return

        # دمج التصحيحات المقترحة مباشرة في corrections الحالية لكل الموظفين
        for payload in result['pending_changes'].values():
            key_base = payload['key_base']
            rev_key = payload['rev_key']
            self._current_corrections.setdefault(key_base, {})
            self._current_corrections[key_base][rev_key] = payload['value']
            self._current_corrections[key_base][f"{rev_key}_role"] = payload['punch_role']

        if self._current_file_id is not None:
            self.correction_state_repo.save(
                self._current_file_id, self._current_corrections, self._current_day_overrides
            )

        self._recompute_dashboard()
        QMessageBox.information(
            self, "تم",
            f"✅ تم تطبيق {len(result['applied'])} تصحيح ذكي بنجاح لكل الموظفين."
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

        state = self.correction_state_repo.load(att_file.id)
        self._current_corrections = state['corrections']
        self._current_day_overrides = state['day_overrides']

        self.setWindowTitle(f"{APP_NAME} — {company_name} ({month:02d}/{year})")

        # [Phase 8]
        self._current_file_bytes = file_bytes
        self._current_file_format = att_file.file_format
        self._current_header_text = f"📂 {company_name} — {ARABIC_MONTHS[month]} {year}"
        self._current_settings = self.file_settings_repo.get_or_create(att_file.id)

        self._run_analysis(
            file_bytes=self._current_file_bytes,
            file_format=self._current_file_format,
            company_id=company_id,
            settings=self._current_settings,
            header_text=self._current_header_text,
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
        self._current_emp_days = emp_days
        self._current_df = df

        # ── مزامنة الموظفين مع القاعدة + تحميل أسعار الساعة المحفوظة ──
        hourly_rates = {}
        self._eid_to_employee_id = {}
        self._eid_to_name = {}

        for _, row in df.iterrows():
            eid = str(row['id'])
            self._eid_to_name[eid] = row.get('name', eid)

            if company_id is not None:
                employee = self.employee_repo.get_or_create(
                    company_id=company_id,
                    external_code=eid,
                    name=row.get('name', ''),
                    department=row.get('department', ''),
                )
                self._eid_to_employee_id[eid] = employee.id

        if company_id is not None:
            self.session.expire_all()
            rates_by_employee_id = self.rate_repo.get_rates_map_by_employee_id(company_id)
            for eid, emp_id in self._eid_to_employee_id.items():
                if emp_id in rates_by_employee_id:
                    hourly_rates[eid] = rates_by_employee_id[emp_id]

        overrides_summary = apply_overrides(
            emp_days, self._current_corrections, self._current_day_overrides
        )

        self.dashboard_page.load_data(header_text, df, overrides_summary, hourly_rates)
        self.stack.setCurrentWidget(self.dashboard_page)
        self.update_pending_status(0)

        # [Phase 8] تحديث لوحة الإعدادات بقيم settings الحالية (بدون إطلاق
        # settings_changed — load_settings تستخدم _loading flag لمنع ده)
        self.settings_panel.load_settings(settings)

    # ══════════════════════════════════════════════════════════════════
    def _recompute_dashboard(self):
        """إعادة حساب overrides_summary وتحديث لوحة التحكم بعد أي تغيير تصحيحات."""
        if self._current_df is None or self._current_emp_days is None:
            return
        overrides_summary = apply_overrides(
            self._current_emp_days, self._current_corrections, self._current_day_overrides
        )
        hourly_rates = dict(self.dashboard_page._hourly_rates)
        header_text = self.dashboard_page.header_label.text()
        self.dashboard_page.load_data(header_text, self._current_df, overrides_summary, hourly_rates)

    # ══════════════════════════════════════════════════════════════════
    def _on_rate_changed(self, eid: str, rate: float):
        if self._current_company_id is None:
            return
        employee_id = self._eid_to_employee_id.get(eid)
        if employee_id is None:
            return
        self.rate_repo.set_rate(self._current_company_id, employee_id, rate)

    # ══════════════════════════════════════════════════════════════════
    # [Phase 8] تغيير أي إعداد شيفت (Cutoff/Saturate/Tolerance/Duplicate)
    # ══════════════════════════════════════════════════════════════════
    def _on_settings_changed(self, new_values: dict):
        if self._current_file_bytes is None or self._current_file_format is None:
            return  # لا يوجد ملف مفتوح حاليًا — الحماية أصلًا موجودة عبر setEnabled(False)

        if self._current_file_id is not None:
            # ملف محفوظ فعليًا (غير Anonymous) → نحفظ في قاعدة البيانات فورًا
            # (نفس فلسفة auto_save_file_state في oldapp.py — بدون زر حفظ منفصل)
            self._current_settings = self.file_settings_repo.update(
                self._current_file_id, **new_values
            )
        else:
            # وضع Anonymous → لا يوجد صف FileSettings بالقاعدة، فنحدّث
            # الكائن الافتراضي في الذاكرة فقط
            for key, value in new_values.items():
                setattr(self._current_settings, key, value)

        # إعادة التحليل الكامل بنفس bytes الملف الحالي مع الإعدادات الجديدة.
        # ملاحظة: هذا يعيد بناء self._current_emp_days من الصفر، لذلك أي
        # تصحيحات يدوية/Day Overrides محفوظة (self._current_corrections /
        # self._current_day_overrides) تُطبَّق تلقائيًا مرة أخرى داخل
        # apply_overrides() كجزء من _run_analysis — لا فقدان بيانات.
        self._run_analysis(
            file_bytes=self._current_file_bytes,
            file_format=self._current_file_format,
            company_id=self._current_company_id,
            settings=self._current_settings,
            header_text=self._current_header_text,
        )

    # ══════════════════════════════════════════════════════════════════
    # شاشة تفاصيل الموظف
    # ══════════════════════════════════════════════════════════════════
    def _on_employee_selected(self, eid: str):
        if not self._current_emp_days or eid not in self._current_emp_days:
            QMessageBox.warning(self, "تنبيه", "لا توجد بيانات لهذا الموظف.")
            return

        days = self._current_emp_days[eid]
        name = self._eid_to_name.get(eid, eid)
        self.employee_detail_page.load_employee(
            eid, name, days, self._current_corrections, self._current_day_overrides
        )
        self.stack.setCurrentWidget(self.employee_detail_page)

    def _on_employee_detail_back(self):
        self.stack.setCurrentWidget(self.dashboard_page)
        self.update_pending_status(0)

    def _on_employee_changes_saved(self, eid: str, corrections: dict, day_overrides: dict):
        """يُستدعى بعد Apply أو Reset داخل EmployeeDetailView."""
        self._current_corrections = corrections
        self._current_day_overrides = day_overrides

        if self._current_file_id is not None:
            self.correction_state_repo.save(
                self._current_file_id, self._current_corrections, self._current_day_overrides
            )

        self._recompute_dashboard()

    def _on_employee_reset(self, eid: str):
        prefix = f"{eid}_"
        self._current_corrections = {
            k: v for k, v in self._current_corrections.items() if not k.startswith(prefix)
        }
        self._current_day_overrides = {
            k: v for k, v in self._current_day_overrides.items() if not k.startswith(prefix)
        }

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
        if (self.stack.currentWidget() is self.employee_detail_page
                and self.employee_detail_page.has_pending_changes()):
            confirm = QMessageBox.warning(
                self, "تعديلات لم تُطبَّق",
                "⚠️ لديك تعديلات لم تُطبَّق بعد. هل تريد الإغلاق على أي حال؟",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if confirm != QMessageBox.Yes:
                event.ignore()
                return
        try:
            self.session.close()
        except Exception:
            pass
        event.accept()
