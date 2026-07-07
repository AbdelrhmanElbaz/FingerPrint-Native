# ui/widgets/settings_panel.py
# لوحة إعدادات الشيفتات الخاصة بالملف/الشهر المفتوح حاليًا — Phase 8.
# نظير قسم "⚙️ الإعدادات" في السايدبار القديم (oldapp.py) و ui.md §3.5.
#
# لا تتعامل مع قاعدة البيانات مباشرة: تستقبل FileSettings (أو الافتراضي في
# وضع Anonymous) عبر load_settings()، وتُطلق settings_changed(dict) عند أي
# تغيير ليتولّى MainWindow حفظه وإعادة التحليل.
#
# ⚠️ device_type_idx / file_format ثابت وقت الاستيراد فقط — لا يوجد هنا أي
# عنصر لتبديله (قرار صريح خارج نطاق Phase 8).

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QSlider, QFrame
)
from PySide6.QtCore import Qt, Signal

OVERNIGHT_WINDOW_MAX = 360  # 6:00 ص — نفس الثابت في oldapp.py


def _fmt_hm(minutes: int) -> str:
    return f"{minutes // 60}:{minutes % 60:02d}"


class _LabeledSlider(QWidget):
    """Slider بخطوة معيّنة + تسمية توضّح القيمة الحالية بصيغة قابلة للقراءة."""

    value_changed = Signal(int)

    def __init__(self, title: str, min_v: int, max_v: int, step: int,
                 fmt_fn=None, parent=None):
        super().__init__(parent)
        self._step = step
        self._fmt_fn = fmt_fn or (lambda v: str(v))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        title_row = QHBoxLayout()
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight:600; font-size:12px;")
        self.value_label = QLabel("")
        self.value_label.setStyleSheet("color:#6c6a64; font-size:12px;")
        title_row.addWidget(self.title_label)
        title_row.addStretch()
        title_row.addWidget(self.value_label)
        layout.addLayout(title_row)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(min_v // step)
        self.slider.setMaximum(max_v // step)
        self.slider.setSingleStep(1)
        self.slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider)

    def _on_slider_changed(self, raw_idx: int):
        actual = raw_idx * self._step
        self.value_label.setText(self._fmt_fn(actual))
        self.value_changed.emit(actual)

    def set_value_silent(self, value: int):
        """يحدّث قيمة الـ Slider بدون إطلاق value_changed (نفس منطق blockSignals
        المستخدم في dashboard_view.py — لمنع إعادة كتابة القيمة المحفوظة أثناء البناء)."""
        idx = round(value / self._step)
        self.slider.blockSignals(True)
        self.slider.setValue(idx)
        self.slider.blockSignals(False)
        self.value_label.setText(self._fmt_fn(idx * self._step))

    def value(self) -> int:
        return self.slider.value() * self._step


class SettingsPanel(QWidget):
    """
    لوحة إعدادات الشيفتات لملف الشهر المفتوح حاليًا.

    Signal:
        settings_changed(dict) — يُطلق عند أي تغيير في أي عنصر، بالقيم التالية:
            {
                'cutoff_hour': float,
                'saturate_minutes': int | None,
                'tolerance_enabled': bool,
                'tolerance_minutes': int,
                'duplicate_punch_tolerance': int,
            }
    """

    settings_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loading = False  # يمنع settings_changed أثناء load_settings()
        self._build_ui()
        self.setEnabled(False)  # معطّل لحد ما يُفتح ملف

    # ══════════════════════════════════════════════════════════════════
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(14)

        title = QLabel("⚙️ إعدادات الشيفتات")
        title.setStyleSheet("font-size:14px; font-weight:700; color:#cc785c;")
        outer.addWidget(title)

        # ── حد بصمات ما بعد منتصف الليل (Redistribute cutoff) ──
        self.cutoff_slider = _LabeledSlider(
            "🌙 حد بصمات ما بعد منتصف الليل",
            min_v=0, max_v=OVERNIGHT_WINDOW_MAX, step=10,
            fmt_fn=_fmt_hm,
        )
        self.cutoff_slider.value_changed.connect(self._emit_changed)
        outer.addWidget(self.cutoff_slider)

        outer.addWidget(self._separator())

        # ── Saturate ──
        self.saturate_checkbox = QCheckBox("⏰ تفعيل حد نهاية اليوم (Saturate)")
        self.saturate_checkbox.stateChanged.connect(self._on_saturate_toggled)
        outer.addWidget(self.saturate_checkbox)

        self.saturate_slider = _LabeledSlider(
            "⏰ حد نهاية اليوم (Saturate)",
            min_v=0, max_v=OVERNIGHT_WINDOW_MAX, step=10,
            fmt_fn=_fmt_hm,
        )
        self.saturate_slider.value_changed.connect(self._emit_changed)
        self.saturate_slider.setVisible(False)
        outer.addWidget(self.saturate_slider)

        outer.addWidget(self._separator())

        # ── تعويض المغادرة المبكرة (Tolerance) ──
        self.tolerance_checkbox = QCheckBox("⚖️ تفعيل تعويض المغادرة المبكرة")
        self.tolerance_checkbox.stateChanged.connect(self._on_tolerance_toggled)
        outer.addWidget(self.tolerance_checkbox)

        self.tolerance_slider = _LabeledSlider(
            "أقصى مدة تسامح",
            min_v=0, max_v=60, step=5,
            fmt_fn=lambda m: f"{m} دقيقة",
        )
        self.tolerance_slider.value_changed.connect(self._emit_changed)
        self.tolerance_slider.setVisible(False)
        outer.addWidget(self.tolerance_slider)

        outer.addWidget(self._separator())

        # ── حذف البصمات المتقاربة ──
        self.dup_slider = _LabeledSlider(
            "🔄 الفارق المسموح بين البصمات المتتالية",
            min_v=1, max_v=60, step=1,
            fmt_fn=lambda m: f"{m} دقيقة",
        )
        self.dup_slider.value_changed.connect(self._emit_changed)
        outer.addWidget(self.dup_slider)

        outer.addStretch()

    def _separator(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:#e6dfd8;")
        return line

    # ══════════════════════════════════════════════════════════════════
    def _on_saturate_toggled(self, _state):
        enabled = self.saturate_checkbox.isChecked()
        self.saturate_slider.setVisible(enabled)
        self._emit_changed()

    def _on_tolerance_toggled(self, _state):
        enabled = self.tolerance_checkbox.isChecked()
        self.tolerance_slider.setVisible(enabled)
        self._emit_changed()

    # ══════════════════════════════════════════════════════════════════
    def _emit_changed(self, *_args):
        if self._loading:
            return
        self.settings_changed.emit(self.current_values())

    def current_values(self) -> dict:
        return {
            'cutoff_hour': self.cutoff_slider.value() / 60,
            'saturate_minutes': (
                self.saturate_slider.value() if self.saturate_checkbox.isChecked() else None
            ),
            'tolerance_enabled': self.tolerance_checkbox.isChecked(),
            'tolerance_minutes': (
                self.tolerance_slider.value() if self.tolerance_checkbox.isChecked() else 0
            ),
            'duplicate_punch_tolerance': self.dup_slider.value(),
        }

    # ══════════════════════════════════════════════════════════════════
    def load_settings(self, settings):
        """
        يملأ العناصر من كائن settings (FileSettings من القاعدة، أو
        _DefaultFileSettings في وضع Anonymous) بدون إطلاق settings_changed.
        """
        self._loading = True
        try:
            cutoff_minutes = round((settings.cutoff_hour or 0) * 60)
            self.cutoff_slider.set_value_silent(cutoff_minutes)

            saturate_min = settings.saturate_minutes
            self.saturate_checkbox.blockSignals(True)
            self.saturate_checkbox.setChecked(saturate_min is not None and saturate_min > 0)
            self.saturate_checkbox.blockSignals(False)
            self.saturate_slider.setVisible(self.saturate_checkbox.isChecked())
            self.saturate_slider.set_value_silent(saturate_min or 60)

            self.tolerance_checkbox.blockSignals(True)
            self.tolerance_checkbox.setChecked(bool(settings.tolerance_enabled))
            self.tolerance_checkbox.blockSignals(False)
            self.tolerance_slider.setVisible(self.tolerance_checkbox.isChecked())
            self.tolerance_slider.set_value_silent(settings.tolerance_minutes or 20)

            self.dup_slider.set_value_silent(settings.duplicate_punch_tolerance or 10)
        finally:
            self._loading = False

        self.setEnabled(True)

    def clear(self):
        """يُستدعى عند إغلاق الملف/الرجوع لشاشة الاستيراد — يعطّل اللوحة."""
        self.setEnabled(False)
