# ui/widgets/bulk_smart_apply_dialog.py
# Preview Dialog لـ Bulk Smart Apply — يعرض البصمات المُقترح تطبيقها تلقائيًا
# (applied) والبصمات المتروكة مع السبب (skipped)، قبل أي تطبيق فعلي.
# نظير قسم "🧠 Bulk Smart Apply" في oldapp.py (bulk_smart_preview expander +
# جدولي applied/skipped + زرّي "✅ تأكيد وتطبيق" / "❌ إلغاء").
#
# لا يعدّل أي حالة بنفسه — فقط يعرض المعاينة ويرجع Accepted/Rejected.
# المُستدعي (EmployeeDetailView) هو المسؤول عن دمج pending_changes الفعلية
# داخل PendingChangesStore بعد القبول.

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView
)


class BulkSmartApplyDialog(QDialog):
    def __init__(self, applied: list, skipped: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🤖 Bulk Smart Apply — معاينة")
        self.resize(720, 480)
        self._build_ui(applied, skipped)

    def _build_ui(self, applied: list, skipped: list):
        layout = QVBoxLayout(self)

        if not applied:
            layout.addWidget(QLabel("لا توجد بصمات تستوفي شروط التطبيق الآمن."))
            close_btn = QPushButton("إغلاق")
            close_btn.clicked.connect(self.reject)
            layout.addWidget(close_btn)
            return

        layout.addWidget(QLabel(f"✅ سيتم اقتراح {len(applied)} تصحيح للتطبيق:"))
        layout.addWidget(self._make_table(
            applied,
            ["اليوم", "البصمة", "النوع", "الثقة", "حجم العينة", "المقترح"],
            lambda item: [
                item['day'], item['ci'], item['type'], item['conf'],
                str(item['sample']), item['suggest'] or '—',
            ],
        ), 1)

        if skipped:
            layout.addWidget(QLabel(f"⏭️ البصمات المتجاهَلة ({len(skipped)}):"))
            layout.addWidget(self._make_table(
                skipped,
                ["اليوم", "البصمة", "السبب"],
                lambda item: [item['day'], item['ci'], item['reason']],
            ), 1)

        btn_row = QHBoxLayout()
        confirm_btn = QPushButton(f"✅ تأكيد وتطبيق {len(applied)} تصحيح")
        confirm_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("❌ إلغاء")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(confirm_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _make_table(self, items: list, headers: list, row_fn) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(len(items))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        for r, item in enumerate(items):
            for c, val in enumerate(row_fn(item)):
                table.setItem(r, c, QTableWidgetItem(str(val)))
        return table
