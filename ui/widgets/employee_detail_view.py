# ui/widgets/employee_detail_view.py
# شاشة تفاصيل الموظف (Phase 5) — نظير show_employee_detail في oldapp.py.
#
# [تعديل 12h] كل الأوقات المعروضة في جدول الأيام أصبحت بصيغة 12 ساعة
# (h:mm ص/م) بدل 24 ساعة الخام — بنفس منطق to_12h/fmt_pair_12h في
# oldapp.py. البيانات المخزَّنة (corrections/day_overrides/raw_times)
# تبقى 24 ساعة داخليًا كما هي؛ التحويل للعرض فقط.
#
# ⚠️ ملاحظة: DayEditorDialog وReviewPanel لسه بيستخدموا QTimeEdit بصيغة
# "hh:mm" (24 ساعة) للإدخال — التعديل ده خاص بعرض الجدول فقط في هذه
# الخطوة. تعديل حقول الإدخال نفسها (بحيث تبقى AM/PM) خطوة تالية منفصلة.

import pandas as pd

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QScrollArea,
    QGridLayout
)
from PySide6.QtCore import Qt, Signal

from services.corrections_engine import (
    apply_overrides, minutes_diff, fmt_hm, bulk_smart_apply_all, to_minutes
)
from ui.state.pending_changes import PendingChangesStore
from ui.widgets.review_panel import ReviewPanel
from ui.widgets.day_editor_dialog import DayEditorDialog
from ui.widgets.bulk_smart_apply_dialog import BulkSmartApplyDialog
from ui.widgets.dashboard_view import KpiCard


# ── [تعديل 12h] نفس دالة to_12h في oldapp.py حرفيًا — تحويل عرض فقط ──────
def _to_12h(t24: str) -> str:
    m = to_minutes(t24)
    if m is None:
        return t24
    hh = (m // 60) % 24
    mm = m % 60
    period = "م" if hh >= 12 else "ص"
    h12 = hh % 12 or 12
    return f"{h12}:{mm:02d} {period}"


class EmployeeDetailView(QWidget):
    back_requested = Signal()             # المستخدم ضغط "رجوع" وتم حل أي تعديلات معلّقة
    changes_saved = Signal(str, dict, dict)   # (eid, corrections, day_overrides) → بعد أي Apply
    reset_requested = Signal(str)         # طلب "استعادة الافتراضي" لهذا الموظف
    pending_count_changed = Signal(int)   # لتحديث StatusBar المركزي في MainWindow

    def __init__(self, parent=None):
        super().__init__(parent)
        self.eid = None
        self.emp_name = ""
        self.days = []
        self.corrections = {}
        self.day_overrides = {}
        self.pending = PendingChangesStore()

        self._build_ui()

    # ══════════════════════════════════════════════════════════════════
    def _build_ui(self):
        outer = QVBoxLayout(self)

        top_row = QHBoxLayout()
        back_btn = QPushButton("← رجوع للقائمة الرئيسية")
        back_btn.clicked.connect(self._on_back_clicked)
        top_row.addWidget(back_btn)

        self.title_label = QLabel("")
        self.title_label.setStyleSheet("font-size:16px; font-weight:700;")
        top_row.addWidget(self.title_label, 1)

        reset_btn = QPushButton("🔄 استعادة الافتراضي")
        reset_btn.clicked.connect(self._on_reset_clicked)
        top_row.addWidget(reset_btn)

        bulk_btn = QPushButton("🤖 Bulk Smart Apply")
        bulk_btn.clicked.connect(self._on_bulk_smart_apply_clicked)
        top_row.addWidget(bulk_btn)
        outer.addLayout(top_row)

        # ── KPIs ──
        kpi_row = QHBoxLayout()
        self.kpi_att = KpiCard("أيام الحضور")
        self.kpi_absent = KpiCard("أيام الغياب")
        self.kpi_hours = KpiCard("ساعات العمل الكلية")
        self.kpi_incomplete = KpiCard("أيام بصمة ناقصة")
        for c in (self.kpi_att, self.kpi_absent, self.kpi_hours, self.kpi_incomplete):
            kpi_row.addWidget(c)
        outer.addLayout(kpi_row)

        # ── لوحة المراجعة ──
        review_box = QFrame()
        review_box.setStyleSheet(
            "QFrame { background:#efe9de; border:1px solid #e6dfd8; border-radius:10px; }"
        )
        review_layout = QVBoxLayout(review_box)
        review_layout.addWidget(QLabel("🔧 مراجعة البصمات الناقصة"))
        self.review_panel = ReviewPanel()
        self.review_panel.change_confirmed.connect(self._on_pending_change_confirmed)
        review_scroll = QScrollArea()
        review_scroll.setWidgetResizable(True)
        review_scroll.setWidget(self.review_panel)
        review_scroll.setMinimumHeight(320)
        review_scroll.setMaximumHeight(480)
        review_layout.addWidget(review_scroll)
        outer.addWidget(review_box)

        # ── جدول الأيام ──
        outer.addWidget(QLabel("📅 تفاصيل الحضور اليومي"))
        self.days_table = QTableWidget()
        self.days_table.setColumnCount(5)
        self.days_table.setHorizontalHeaderLabels(
            ["اليوم", "الحالة", "فترات الحضور", "إجمالي الساعات", "تعديل"]
        )
        self.days_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.days_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.days_table.setSelectionBehavior(QTableWidget.SelectRows)
        outer.addWidget(self.days_table, 1)

        # ── شريط Apply/Discard المحلي ──
        apply_row = QHBoxLayout()
        self.pending_label = QLabel("")
        apply_row.addWidget(self.pending_label, 1)
        self.apply_btn = QPushButton("✅ Apply")
        self.apply_btn.clicked.connect(self._on_apply_clicked)
        self.discard_btn = QPushButton("🗑️ تجاهل التعديلات")
        self.discard_btn.clicked.connect(self._on_discard_clicked)
        apply_row.addWidget(self.apply_btn)
        apply_row.addWidget(self.discard_btn)
        outer.addLayout(apply_row)

    # ══════════════════════════════════════════════════════════════════
    def load_employee(self, eid: str, emp_name: str, days: list,
                       corrections: dict, day_overrides: dict):
        """يُستدعى من MainWindow عند فتح تفاصيل موظف."""
        self.eid = eid
        self.emp_name = emp_name
        self.days = days
        self.corrections = corrections or {}
        self.day_overrides = day_overrides or {}
        self.pending.clear()

        self.title_label.setText(f"👤 تحليل الموظف: {emp_name} (ID: {eid})")
        self._refresh_all()

    # ══════════════════════════════════════════════════════════════════
    def _refresh_all(self):
        self._refresh_kpis()
        self._refresh_review_panel()
        self._refresh_days_table()
        self._refresh_pending_bar()

    def _refresh_kpis(self):
        summary = apply_overrides(
            {self.eid: self.days}, self.corrections, self.day_overrides, self.pending.get_all()
        ).get(self.eid, {})
        att = summary.get('attendance_days', 0)
        work_h = summary.get('work_hours', 0)
        self.kpi_att.set_value(str(round(att, 1)))
        self.kpi_absent.set_value(str(int(summary.get('absent_days', 0))))
        self.kpi_hours.set_value(fmt_hm(round(work_h * 60)))
        self.kpi_incomplete.set_value(str(int(summary.get('incomplete_days', 0))))

    def _refresh_review_panel(self):
        self.review_panel.rebuild(
            self.eid, self.days, self.corrections, self.day_overrides, self.pending.get_all()
        )

    def _refresh_days_table(self):
        pending_all = self.pending.get_all()
        self.days_table.setRowCount(len(self.days))

        for di, d in enumerate(self.days):
            key_base = f"{self.eid}_{di}"

            pending_ov = None
            for pv in pending_all.values():
                if pv.get('type') == 'day_override' and pv.get('key_base') == key_base:
                    pending_ov = pv['data']

            ov_day = self.day_overrides.get(key_base) or pending_ov
            is_pending_ov = pending_ov is not None and key_base not in self.day_overrides

            if ov_day:
                status = ov_day.get('status', '')
                pairs = ov_day.get('pairs') or []
                total = sum((minutes_diff(a, b) or 0) for a, b in pairs)
                # [تعديل 12h]
                punches_str = (
                    "  |  ".join(f"{_to_12h(a)} ← {_to_12h(b)}" for a, b in pairs)
                    if pairs else "—"
                )
                hours_str = fmt_hm(total) if total else "—"
            else:
                day_corrections = self.corrections.get(key_base, {})
                base_min = sum(m for _, m in d['punch_pairs'])
                extra_min = 0
                still_inc = False
                # [تعديل 12h] كل عنصر من punch_pairs الأصلية بصيغة "HH:MM→HH:MM"
                pairs_disp = []
                for pstr, _pm in d['punch_pairs']:
                    parts = pstr.rstrip("✓").strip().split("→")
                    if len(parts) == 2:
                        pairs_disp.append(f"{_to_12h(parts[0].strip())} ← {_to_12h(parts[1].strip())}")
                    else:
                        pairs_disp.append(_to_12h(pstr))

                for ri, rev in enumerate(d.get('needs_review', [])):
                    rev_key = f"{key_base}_r{ri}"
                    resolved_time = day_corrections.get(rev_key)
                    pending_key = f"corr_{key_base}_{ri}"
                    pending_val = pending_all.get(pending_key, {}).get('value')
                    actual_resolved = resolved_time or pending_val
                    if actual_resolved:
                        role = day_corrections.get(f"{rev_key}_role") or \
                            pending_all.get(pending_key, {}).get('punch_role', 'check_in')
                        if role == 'check_out':
                            diff = minutes_diff(actual_resolved, rev['ci'])
                            # [تعديل 12h]
                            pairs_disp.append(f"{_to_12h(actual_resolved)} ← {_to_12h(rev['ci'])}")
                        else:
                            diff = minutes_diff(rev['ci'], actual_resolved)
                            # [تعديل 12h]
                            pairs_disp.append(f"{_to_12h(rev['ci'])} ← {_to_12h(actual_resolved)}")
                        if diff is not None:
                            extra_min += diff
                    else:
                        still_inc = True
                        # [تعديل 12h]
                        pairs_disp.append(f"⚠️ {_to_12h(rev['ci'])} (ناقصة)")

                total = base_min + extra_min
                status = d['status']
                if status == 'غياب' and total > 0:
                    status = 'حضور'
                punches_str = "  |  ".join(pairs_disp) if pairs_disp else "—"
                hours_str = fmt_hm(total) if total else "—"
                is_pending_ov = False
                if still_inc:
                    status += "  ⚠️"

            self.days_table.setItem(di, 0, QTableWidgetItem(d['day']))
            self.days_table.setItem(di, 1, QTableWidgetItem(status))
            self.days_table.setItem(di, 2, QTableWidgetItem(punches_str))
            self.days_table.setItem(di, 3, QTableWidgetItem(hours_str))

            edit_btn = QPushButton("⏳✏️" if is_pending_ov else "✏️")
            edit_btn.clicked.connect(lambda _c=False, _di=di: self._open_day_editor(_di))
            self.days_table.setCellWidget(di, 4, edit_btn)

    def _refresh_pending_bar(self):
        n = self.pending.count()
        if n > 0:
            self.pending_label.setText(f"⏳ {n} تعديل معلَّق بانتظار Apply")
        else:
            self.pending_label.setText("")
        self.apply_btn.setEnabled(n > 0)
        self.discard_btn.setEnabled(n > 0)
        self.pending_count_changed.emit(n)

    # ══════════════════════════════════════════════════════════════════
    def _on_pending_change_confirmed(self, pending_key: str, pending_data: dict):
        self.pending.add(pending_key, pending_data)
        self._refresh_all()

    def _open_day_editor(self, di: int):
        d = self.days[di]
        key_base = f"{self.eid}_{di}"

        existing = self.day_overrides.get(key_base)
        for pv in self.pending.get_all().values():
            if pv.get('type') == 'day_override' and pv.get('key_base') == key_base:
                existing = pv['data']

        dialog = DayEditorDialog(
            day_label=d['day'],
            existing_override=existing,
            raw_times=d.get('raw_times', []),
            punch_pairs=d.get('punch_pairs', []),
            parent=self,
        )
        if dialog.exec():
            pending_key = f"dayov_{key_base}"
            if dialog.result_status is None:
                # "بدون تعديل" — إزالة أي override موجود
                if key_base in self.day_overrides:
                    self.pending.add(pending_key, {
                        'type': 'remove_override', 'key_base': key_base,
                    })
                else:
                    self.pending.remove(pending_key)
            else:
                self.pending.add(pending_key, {
                    'type': 'day_override', 'key_base': key_base,
                    'data': {'status': dialog.result_status, 'pairs': dialog.result_pairs},
                })
            self._refresh_all()

    # ══════════════════════════════════════════════════════════════════
    def _on_apply_clicked(self):
        pending_all = self.pending.get_all()
        for pv in pending_all.values():
            ptype = pv.get('type')
            if ptype == 'correction':
                kb = pv['key_base']
                self.corrections.setdefault(kb, {})
                self.corrections[kb][pv['rev_key']] = pv['value']
                self.corrections[kb][f"{pv['rev_key']}_role"] = pv.get('punch_role', 'check_in')
            elif ptype == 'day_override':
                self.day_overrides[pv['key_base']] = pv['data']
            elif ptype == 'remove_override':
                self.day_overrides.pop(pv['key_base'], None)

        self.pending.clear()
        self.changes_saved.emit(self.eid, self.corrections, self.day_overrides)
        self._refresh_all()
        QMessageBox.information(self, "تم", "✅ تم تطبيق التعديلات بنجاح")

    def _on_discard_clicked(self):
        self.pending.clear()
        self._refresh_all()

    # ══════════════════════════════════════════════════════════════════
    def _on_bulk_smart_apply_clicked(self):
        """
        تشغيل bulk_smart_apply_all على بيانات هذا الموظف فقط (نطاق الشاشة
        الحالية)، عرض معاينة في BulkSmartApplyDialog، وعند التأكيد فقط:
        دمج pending_changes الراجعة في PendingChangesStore الحالي — لا تعديل
        فعلي على corrections/day_overrides قبل ضغط "تأكيد وتطبيق" داخل الـ Dialog،
        وبعده لسه محتاج المستخدم يضغط "✅ Apply" الرئيسي عشان يتثبّت (نفس فلسفة
        باقي الشاشة: pending أولًا، Apply يحفظ فعليًا).
        """
        result = bulk_smart_apply_all(
            {self.eid: self.days},
            self.corrections,
            self.pending.get_all(),
            self.day_overrides,
            min_sample=3,
        )
        dialog = BulkSmartApplyDialog(result['applied'], result['skipped'], parent=self)
        if dialog.exec() and result['applied']:
            for pending_key, payload in result['pending_changes'].items():
                self.pending.add(pending_key, payload)
            self._refresh_all()

    # ══════════════════════════════════════════════════════════════════
    def _on_reset_clicked(self):
        confirm = QMessageBox.warning(
            self, "تأكيد",
            f"⚠️ سيتم حذف كل تصحيحات وتعديلات الموظف {self.emp_name} نهائيًا. "
            "هذا لا يمكن التراجع عنه.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return
        self.corrections = {}
        self.day_overrides = {}
        self.pending.clear()
        self.reset_requested.emit(self.eid)
        self.changes_saved.emit(self.eid, self.corrections, self.day_overrides)
        self._refresh_all()

    # ══════════════════════════════════════════════════════════════════
    def has_pending_changes(self) -> bool:
        return self.pending.count() > 0

    def _on_back_clicked(self):
        if not self.has_pending_changes():
            self.back_requested.emit()
            return

        n = self.pending.count()
        box = QMessageBox(self)
        box.setWindowTitle("تعديلات لم تُطبَّق")
        box.setText(f"⚠️ لديك {n} تعديل لم يُطبَّق بعد! هل تريد حفظه قبل المغادرة؟")
        save_btn = box.addButton("💾 حفظ وانتقال", QMessageBox.AcceptRole)
        discard_btn = box.addButton("🗑️ تجاهل وانتقال", QMessageBox.DestructiveRole)
        cancel_btn = box.addButton("❌ إلغاء (ابقَ)", QMessageBox.RejectRole)
        box.exec()

        clicked = box.clickedButton()
        if clicked == save_btn:
            self._on_apply_clicked()
            self.back_requested.emit()
        elif clicked == discard_btn:
            self._on_discard_clicked()
            self.back_requested.emit()
        # cancel_btn → لا نفعل شيء، نبقى في الصفحة
