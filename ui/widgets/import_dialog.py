# ui/widgets/import_dialog.py
# نافذة استيراد ملف حضور جديد (Hikvision / ZK Classic) — بديل Import View في Streamlit.
# تدعم: اختيار ملف (زر أو Drag&Drop)، اختيار شركة موجودة أو جديدة، سنة، شهر،
#       وضع "فتح مؤقت (Anonymous)" بدون حفظ.
#
# يعتمد على:
#   CompanyRepository.list_all() -> list[Company]
#   CompanyRepository.create(name: str) -> Company   (تُنشئ أو تُرجع الموجودة بنفس الاسم)
#   AttendanceFileRepository.create(company_id, year, month, file_format,
#                                    original_file_path, working_file_path,
#                                    is_anonymous) -> AttendanceFile
#
# ملاحظة: حفظ bytes الملف الفعلي على القرص (original/working) لا تقوم به
# AttendanceFileRepository — هي فقط تخزّن المسارات في القاعدة. لذلك نتولى
# نحن هنا كتابة الملف على القرص أولاً ثم نمرر مساراته للـ Repository.

import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QSpinBox, QCheckBox, QFileDialog, QMessageBox,
    QFrame, QProgressDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent

ARABIC_MONTHS = [
    '', 'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
    'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'
]

NEW_COMPANY_LABEL = "➕ شركة جديدة"


class DropZoneLabel(QFrame):
    """منطقة سحب-وإفلات بسيطة لملف xls/xlsx."""

    file_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumHeight(90)
        self.setStyleSheet(
            "QFrame { border: 2px dashed #e6dfd8; border-radius: 12px; background: #efe9de; }"
        )
        layout = QVBoxLayout(self)
        self.label = QLabel("📤 اسحب ملف الحضور هنا أو اضغط 'اختيار ملف'")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if not urls:
            return
        path = urls[0].toLocalFile()
        if path.lower().endswith((".xls", ".xlsx")):
            self.file_dropped.emit(path)
        else:
            QMessageBox.warning(self, "صيغة غير مدعومة", "الرجاء اختيار ملف .xls أو .xlsx فقط")

    def set_file_name(self, name: str):
        self.label.setText(f"✅ {name}")


class ImportDialog(QDialog):
    """
    نافذة استيراد ملف حضور جديد.

    Signal:
        import_completed(payload: dict)
            payload = {
                'is_anonymous': bool,
                'file_bytes': bytes,
                'company_id': int | None,
                'company_name': str | None,
                'year': int | None,
                'month': int | None,
                'file_format': 'hikvision' | 'zk_classic',
            }
        يُطلق بعد نجاح الاستيراد — على MainWindow استقباله وتشغيل التحليل الفعلي.
    """

    import_completed = Signal(dict)

    def __init__(self, company_repo, attendance_repo, parent=None):
        super().__init__(parent)
        self.company_repo = company_repo
        self.attendance_repo = attendance_repo
        self.selected_file_path = None

        self.setWindowTitle("📤 استيراد ملف حضور جديد")
        self.setLayoutDirection(Qt.RightToLeft)
        self.setMinimumWidth(480)

        self._build_ui()

    # ──────────────────────────────────────────────────────────────────
    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ── منطقة اختيار الملف ──
        self.drop_zone = DropZoneLabel()
        self.drop_zone.file_dropped.connect(self._set_file)
        layout.addWidget(self.drop_zone)

        browse_btn = QPushButton("📁 اختيار ملف")
        browse_btn.clicked.connect(self._browse_file)
        layout.addWidget(browse_btn)

        # ── وضع الجهاز (Hikvision / ZK Classic) ──
        form_device = QFormLayout()
        self.device_combo = QComboBox()
        self.device_combo.addItems(["Main Fingerprint (ZK Classic)", "HikVision"])
        form_device.addRow("🖥️ نوع جهاز البصمة:", self.device_combo)
        layout.addLayout(form_device)

        # ── وضع Anonymous ──
        self.anon_checkbox = QCheckBox("📤 فتح مؤقت (Anonymous) — بدون حفظ في بيانات البرنامج")
        self.anon_checkbox.stateChanged.connect(self._on_anon_toggled)
        layout.addWidget(self.anon_checkbox)

        # ── بيانات الاستيراد (شركة/سنة/شهر) ──
        self.form_frame = QFrame()
        form = QFormLayout(self.form_frame)

        self.company_combo = QComboBox()
        self.company_combo.setEditable(False)
        self.company_combo.currentTextChanged.connect(self._on_company_changed)
        form.addRow("🏢 الشركة:", self.company_combo)

        self.new_company_input = QLineEdit()
        self.new_company_input.setPlaceholderText("اسم الشركة الجديدة")
        self.new_company_input.hide()
        form.addRow("", self.new_company_input)

        today = datetime.date.today()

        self.year_spin = QSpinBox()
        self.year_spin.setRange(2020, 2100)
        self.year_spin.setValue(today.year)
        form.addRow("📅 السنة:", self.year_spin)

        self.month_spin = QSpinBox()
        self.month_spin.setRange(1, 12)
        self.month_spin.setValue(today.month)
        form.addRow("📆 الشهر:", self.month_spin)

        layout.addWidget(self.form_frame)
        self._reload_companies()

        # ── أزرار التأكيد ──
        btn_row = QHBoxLayout()
        self.import_btn = QPushButton("💾 حفظ واستيراد")
        self.import_btn.setDefault(True)
        self.import_btn.clicked.connect(self._do_import)
        cancel_btn = QPushButton("إلغاء")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.import_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    # ──────────────────────────────────────────────────────────────────
    def _reload_companies(self):
        self.company_combo.clear()
        companies = self.company_repo.list_all()
        names = [c.name for c in companies]
        self.company_combo.addItems(names + [NEW_COMPANY_LABEL])
        if not names:
            self.company_combo.setCurrentText(NEW_COMPANY_LABEL)

    # ──────────────────────────────────────────────────────────────────
    def _on_company_changed(self, text: str):
        self.new_company_input.setVisible(text == NEW_COMPANY_LABEL)

    # ──────────────────────────────────────────────────────────────────
    def _on_anon_toggled(self, checked_state):
        is_anon = bool(checked_state)
        self.form_frame.setVisible(not is_anon)
        self.import_btn.setText("📤 فتح للمراجعة" if is_anon else "💾 حفظ واستيراد")

    # ──────────────────────────────────────────────────────────────────
    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "اختر ملف الحضور", "", "Excel Files (*.xls *.xlsx)"
        )
        if path:
            self._set_file(path)

    def _set_file(self, path: str):
        self.selected_file_path = path
        self.drop_zone.set_file_name(Path(path).name)

    # ──────────────────────────────────────────────────────────────────
    def _do_import(self):
        if not self.selected_file_path:
            QMessageBox.warning(self, "ملف مفقود", "الرجاء اختيار ملف أولاً.")
            return

        file_format = "hikvision" if self.device_combo.currentIndex() == 1 else "zk_classic"
        is_anon = self.anon_checkbox.isChecked()

        try:
            with open(self.selected_file_path, "rb") as f:
                file_bytes = f.read()
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"تعذّرت قراءة الملف:\n{e}")
            return

        if is_anon:
            payload = {
                "is_anonymous": True,
                "file_bytes": file_bytes,
                "company_id": None,
                "company_name": None,
                "year": None,
                "month": None,
                "file_format": file_format,
            }
            self.import_completed.emit(payload)
            self.accept()
            return

        # ── وضع الحفظ الدائم ──
        company_text = self.company_combo.currentText()
        if company_text == NEW_COMPANY_LABEL:
            company_name = self.new_company_input.text().strip().upper()
            if not company_name:
                QMessageBox.warning(self, "بيانات ناقصة", "الرجاء إدخال اسم الشركة الجديدة.")
                return
        else:
            company_name = company_text.strip().upper()

        year = self.year_spin.value()
        month = self.month_spin.value()

        progress = QProgressDialog("جاري حفظ الملف...", None, 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setCancelButton(None)
        progress.show()

        try:
            # 1) إنشاء/جلب الشركة
            company = self.company_repo.create(company_name)

            # 2) تجهيز مسار التخزين: data/<company>/<year>/<month>/
            data_root = Path(__file__).resolve().parent.parent.parent / "data"
            month_dir = data_root / company.name / str(year) / f"{month:02d}"
            month_dir.mkdir(parents=True, exist_ok=True)

            base_name = f"{company.name}_{year}_{month:02d}"
            original_path = month_dir / f"{base_name}_original.bin"
            working_path = month_dir / f"{base_name}.xlsx"

            if not original_path.exists():
                original_path.write_bytes(file_bytes)
            working_path.write_bytes(file_bytes)

            # 3) هل يوجد ملف بنفس الشهر/السنة لهذه الشركة بالفعل؟
            existing = self.attendance_repo.get_by_company_year_month(company.id, year, month)
            if existing:
                confirm = QMessageBox.question(
                    self, "الملف موجود بالفعل",
                    f"يوجد ملف محفوظ بالفعل لـ {company.name} — {month:02d}/{year}.\n"
                    "هل تريد استبداله بهذا الملف الجديد؟",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                if confirm != QMessageBox.Yes:
                    progress.close()
                    return
                # نحدّث working_file فقط (النسخة الأصلية القديمة تبقى كما هي)
                existing.working_file_path = str(working_path)
                self.attendance_repo.session.commit()
                attendance_file = existing
            else:
                attendance_file = self.attendance_repo.create(
                    company_id=company.id,
                    year=year,
                    month=month,
                    file_format=file_format,
                    original_file_path=str(original_path),
                    working_file_path=str(working_path),
                    is_anonymous=False,
                )

        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "خطأ", f"فشل حفظ الملف:\n{e}")
            return

        progress.close()

        payload = {
            "is_anonymous": False,
            "file_bytes": file_bytes,
            "company_id": company.id,
            "company_name": company.name,
            "year": year,
            "month": month,
            "file_format": file_format,
            "attendance_file_id": attendance_file.id,
        }
        self.import_completed.emit(payload)
        self.accept()
