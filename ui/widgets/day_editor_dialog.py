# ui/widgets/day_editor_dialog.py
# Dialog لاستبدال يوم عمل كامل — نظير show_day_editor في oldapp.py.
#
# [تعديل 12h] استُبدل QTimeEdit (24 ساعة) بحقول "ساعة / دقيقة / ص-م" منفصلة
# — نفس أسلوب time_input_12h في oldapp.py بالضبط. البيانات المخزَّنة
# داخليًا (result_pairs) تبقى بصيغة 24 ساعة "HH:MM" كما هي (from_12h يحوّل
# عند القراءة)؛ فقط طريقة الإدخال المرئية اتغيّرت.

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QFrame, QDialogButtonBox,
    QScrollArea, QWidget
)
from PySide6.QtCore import Qt

from services.corrections_engine import to_minutes, minutes_diff, fmt_hm


def _to_12h(t24: str) -> str:
    m = to_minutes(t24)
    if m is None:
        return t24
    hh = (m // 60) % 24
    mn = m % 60
    period = "م" if hh >= 12 else "ص"
    h12    = hh % 12 or 12
    return f"{h12}:{mn:02d} {period}"


def _from_12h(h: int, mn: int, period: str) -> str:
    """نفس from_12h في oldapp.py حرفيًا."""
    h = int(h); mn = int(mn)
    if period == "ص":
        hh24 = 0 if h == 12 else h
    else:
        hh24 = 12 if h == 12 else h + 12
    return f"{hh24:02d}:{mn:02d}"


def _split_24h(t: str):
    """يفكّك 'HH:MM' (24h) لـ (hour_12, minute, period) — لتعمير حقول الإدخال."""
    m = to_minutes(t)
    if m is None:
        return 8, 0, "ص"
    hh = (m // 60) % 24
    mm = m % 60
    period = "م" if hh >= 12 else "ص"
    h12 = hh % 12 or 12
    return h12, mm, period


class _TimeInput12h(QWidget):
    """
    حقل إدخال وقت بصيغة 12 ساعة: Spinbox للساعة (1-12) + Spinbox للدقيقة
    (0-59) + Combo لـ ص/م. بديل QTimeEdit — نفس فلسفة time_input_12h في
    oldapp.py لكن كـ QWidget مركّب قابل لإعادة الاستخدام.
    """

    def __init__(self, existing_24h: str = "", parent=None):
        super().__init__(parent)
        h12, mm, period = _split_24h(existing_24h) if existing_24h else (8, 0, "ص")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.hour_spin = QSpinBox()
        self.hour_spin.setRange(1, 12)
        self.hour_spin.setValue(h12)
        self.hour_spin.setFixedWidth(50)
        layout.addWidget(self.hour_spin)

        layout.addWidget(QLabel(":"))

        self.minute_spin = QSpinBox()
        self.minute_spin.setRange(0, 59)
        self.minute_spin.setValue(mm)
        self.minute_spin.setFixedWidth(50)
        # عرض الدقيقة بصفرين دايمًا (01, 05...) — QSpinBox ما بيدعمش format
        # مباشر، فبنستخدم prefix/suffix خدعة بسيطة: نتحكم بالعرض عبر textFromValue
        self.minute_spin.setWrapping(True)
        layout.addWidget(self.minute_spin)

        self.period_combo = QComboBox()
        self.period_combo.addItems(["ص", "م"])
        self.period_combo.setCurrentText(period)
        self.period_combo.setFixedWidth(55)
        layout.addWidget(self.period_combo)

        layout.addStretch()

        # ربط الإشارات بإشارة موحّدة عشان نقدر نراقب أي تغيير من بره
        self.hour_spin.valueChanged.connect(self._emit_changed)
        self.minute_spin.valueChanged.connect(self._emit_changed)
        self.period_combo.currentTextChanged.connect(self._emit_changed)

        self._on_changed_callback = None

    def _emit_changed(self, *_args):
        if self._on_changed_callback:
            self._on_changed_callback()

    def set_on_changed(self, callback):
        self._on_changed_callback = callback

    def value_24h(self) -> str:
        return _from_12h(
            self.hour_spin.value(), self.minute_spin.value(), self.period_combo.currentText()
        )

    def set_value_24h(self, t24: str):
        h12, mm, period = _split_24h(t24)
        self.hour_spin.blockSignals(True)
        self.minute_spin.blockSignals(True)
        self.period_combo.blockSignals(True)
        self.hour_spin.setValue(h12)
        self.minute_spin.setValue(mm)
        self.period_combo.setCurrentText(period)
        self.hour_spin.blockSignals(False)
        self.minute_spin.blockSignals(False)
        self.period_combo.blockSignals(False)


class DayEditorDialog(QDialog):
    """
    يفتح نافذة لتعديل يوم معيّن:
      - بدون تعديل (result_status = None)
      - حضور (result_status = 'حضور', result_pairs = [(in, out), ...])
      - غياب (result_status = 'غياب', result_pairs = [])
    """

    def __init__(self, day_label: str, existing_override: dict | None,
                 raw_times: list, punch_pairs: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"تعديل يوم {day_label}")
        self.setLayoutDirection(Qt.RightToLeft)
        self.setMinimumWidth(480)
        self.resize(520, 500)

        self.result_status = None
        self.result_pairs  = []

        # ── البيانات الأولية ──
        self._day_label       = day_label
        self._raw_times       = raw_times
        self._punch_pairs     = punch_pairs
        self._existing        = existing_override  # dict | None

        self._pair_widgets: list[tuple] = []  # (in_input, out_input) — _TimeInput12h

        self._build_ui()

    # ══════════════════════════════════════════════════════════════════
    def _build_ui(self):
        outer = QVBoxLayout(self)

        # ── عرض البصمات الخام ──
        if self._raw_times:
            raw_str = "  ،  ".join(_to_12h(t) for t in self._raw_times)
            info = QLabel(f"📍 البصمات الخام ({len(self._raw_times)}): {raw_str}")
            info.setWordWrap(True)
            info.setStyleSheet("color:#6c6a64; font-size:12px;")
            outer.addWidget(info)

        # ── الاختيار الرئيسي ──
        status_row = QHBoxLayout()
        status_row.addWidget(QLabel("الحالة الجديدة:"))
        self.status_combo = QComboBox()
        self.status_combo.addItems(["بدون تعديل", "حضور", "غياب"])

        if self._existing:
            if self._existing.get('status') == 'حضور':
                self.status_combo.setCurrentIndex(1)
            else:
                self.status_combo.setCurrentIndex(2)
        else:
            self.status_combo.setCurrentIndex(0)

        self.status_combo.currentIndexChanged.connect(self._on_status_changed)
        status_row.addWidget(self.status_combo)
        status_row.addStretch()
        outer.addLayout(status_row)

        # ── منطقة الأزواج (تظهر فقط عند اختيار "حضور") ──
        self.pairs_container = QWidget()
        self.pairs_layout = QVBoxLayout(self.pairs_container)
        self.pairs_layout.setSpacing(8)

        n_row = QHBoxLayout()
        n_row.addWidget(QLabel("عدد فترات الحضور:"))
        self.n_spin = QSpinBox()
        self.n_spin.setRange(1, 6)
        self.n_spin.setValue(max(1, len(self._punch_pairs) or 1))
        self.n_spin.valueChanged.connect(self._rebuild_pairs)
        n_row.addWidget(self.n_spin)
        n_row.addStretch()
        self.pairs_layout.addLayout(n_row)

        self.pairs_frame = QWidget()
        self.pairs_frame_layout = QVBoxLayout(self.pairs_frame)
        self.pairs_frame_layout.setSpacing(6)
        self.pairs_layout.addWidget(self.pairs_frame)

        self.preview_lbl = QLabel("")
        self.preview_lbl.setStyleSheet("color:#3c7a4c; font-weight:600;")
        self.pairs_layout.addWidget(self.preview_lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.pairs_container)
        scroll.setMaximumHeight(260)
        outer.addWidget(scroll)

        # ── أزرار Dialog ──
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("✅ تأكيد")
        btns.button(QDialogButtonBox.Cancel).setText("❌ إلغاء")
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        outer.addWidget(btns)

        self._on_status_changed(self.status_combo.currentIndex())

    # ══════════════════════════════════════════════════════════════════
    def _on_status_changed(self, idx: int):
        show_pairs = (idx == 1)  # "حضور"
        self.pairs_container.setVisible(show_pairs)
        if show_pairs:
            self._rebuild_pairs()

    def _rebuild_pairs(self):
        while self.pairs_frame_layout.count():
            item = self.pairs_frame_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._pair_widgets.clear()

        n = self.n_spin.value()

        init_pairs = []
        if self._existing and self._existing.get('pairs'):
            init_pairs = self._existing['pairs']
        elif self._punch_pairs:
            for pstr, _ in self._punch_pairs:
                parts = pstr.rstrip("✓").strip().split("→")
                if len(parts) == 2:
                    init_pairs.append((parts[0].strip(), parts[1].strip()))
                else:
                    init_pairs.append((parts[0].strip(), ""))

        for i in range(n):
            exist_in  = init_pairs[i][0] if i < len(init_pairs) else ""
            exist_out = init_pairs[i][1] if i < len(init_pairs) else ""

            sep = QFrame()
            sep.setStyleSheet(
                "QFrame { background:#efe9de; border:1px solid #e6dfd8; "
                "border-radius:6px; padding:4px; }"
            )
            sep_layout = QHBoxLayout(sep)

            sep_layout.addWidget(QLabel(f"الفترة {i + 1}:"))

            # [تعديل 12h] _TimeInput12h بدل QTimeEdit
            sep_layout.addWidget(QLabel("دخول"))
            in_input = _TimeInput12h(existing_24h=exist_in or "08:00")
            in_input.set_on_changed(self._update_preview)
            sep_layout.addWidget(in_input)

            sep_layout.addWidget(QLabel("انصراف"))
            out_input = _TimeInput12h(existing_24h=exist_out or "17:00")
            out_input.set_on_changed(self._update_preview)
            sep_layout.addWidget(out_input)

            self.pairs_frame_layout.addWidget(sep)
            self._pair_widgets.append((in_input, out_input))

        self._update_preview()

    def _update_preview(self):
        total = 0
        for in_i, out_i in self._pair_widgets:
            t_in  = in_i.value_24h()
            t_out = out_i.value_24h()
            diff  = minutes_diff(t_in, t_out)
            if diff is not None:
                total += diff
        self.preview_lbl.setText(f"⏱️ إجمالي الساعات: {fmt_hm(total)}")

    # ══════════════════════════════════════════════════════════════════
    def _on_ok(self):
        idx = self.status_combo.currentIndex()
        if idx == 0:
            self.result_status = None
            self.result_pairs  = []
        elif idx == 1:
            self.result_status = 'حضور'
            self.result_pairs  = [
                (in_i.value_24h(), out_i.value_24h())
                for in_i, out_i in self._pair_widgets
            ]
        else:
            self.result_status = 'غياب'
            self.result_pairs  = []
        self.accept()
