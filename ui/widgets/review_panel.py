# ui/widgets/review_panel.py
# لوحة مراجعة البصمات الناقصة — نظير show_review_panel في oldapp.py.
# تعرض كل بصمة تحتاج مراجعة (بصمة واحدة بلا زوج) مع:
#   - تشخيص تلقائي (حضور/انصراف) + مستوى الثقة
#   - اقتراح ذكي بالوقت المقابل
#   - إدخال يدوي للوقت الناقص
#   - زر تأكيد يُطلق Signal للـ EmployeeDetailView
#
# لا تُطبّق التصحيحات بنفسها — تُطلق change_confirmed(key, data) فقط.

import math

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTimeEdit, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTime

from services.corrections_engine import to_minutes, minutes_diff, fmt_hm


# ─── دوال مساعدة ──────────────────────────────────────────────────────────────

def _circular_mean(minutes_list: list) -> int:
    if not minutes_list:
        return 0
    n = len(minutes_list)
    sin_sum = sum(math.sin(2 * math.pi * m / 1440) for m in minutes_list)
    cos_sum = sum(math.cos(2 * math.pi * m / 1440) for m in minutes_list)
    angle   = math.atan2(sin_sum / n, cos_sum / n)
    return int(round(angle * 1440 / (2 * math.pi)) % 1440)


def _circular_dist(a: int, b: int) -> int:
    d = abs(a - b)
    return min(d, 1440 - d)


def _classify_lone_punch(ci: str, all_days: list, shift_pattern=None) -> dict:
    """نظير classify_lone_punch في oldapp.py."""
    lone_min = to_minutes(ci)
    if lone_min is None:
        return {'type': 'unknown', 'confidence': 'low', 'avg_in': None, 'avg_out': None,
                'corr_suggestion': None, 'corr_sample_size': 0}

    relevant = [d for d in all_days if shift_pattern is None or d.get('shift_pattern') == shift_pattern]
    check_in_mins, check_out_mins, pairs_list = [], [], []

    for d in relevant:
        times = d.get('raw_times', [])
        if len(times) >= 2:
            fm = to_minutes(times[0])
            lm = to_minutes(times[-1])
            if fm is not None:
                check_in_mins.append(fm)
            if lm is not None:
                check_out_mins.append(lm)
            for i in range(0, len(times) - 1, 2):
                in_m  = to_minutes(times[i])
                out_m = to_minutes(times[i + 1])
                if in_m is not None and out_m is not None:
                    raw_diff = out_m - in_m
                    if raw_diff < 0:
                        raw_diff += 1440
                    if 2 <= raw_diff <= 960:
                        pairs_list.append((in_m, out_m))

    if not check_in_mins or not check_out_mins:
        if shift_pattern is not None:
            return _classify_lone_punch(ci, all_days, shift_pattern=None)
        return {'type': 'unknown', 'confidence': 'low', 'avg_in': None, 'avg_out': None,
                'corr_suggestion': None, 'corr_sample_size': 0}

    avg_in  = _circular_mean(check_in_mins)
    avg_out = _circular_mean(check_out_mins)
    dist_in  = _circular_dist(lone_min, avg_in)
    dist_out = _circular_dist(lone_min, avg_out)

    if dist_in < dist_out:
        punch_type = 'check_in'
        confidence = 'high' if (dist_out - dist_in) > 30 else 'low'
    elif dist_out < dist_in:
        punch_type = 'check_out'
        confidence = 'high' if (dist_in - dist_out) > 30 else 'low'
    else:
        punch_type = 'unknown'
        confidence = 'low'

    WINDOW = 45
    corr_suggestion, corr_sample_size = None, 0
    if punch_type == 'check_in' and pairs_list:
        matching = [o for (inp, o) in pairs_list if _circular_dist(inp, lone_min) <= WINDOW]
        if matching:
            corr_suggestion  = _fmt_hm(_circular_mean(matching))
            corr_sample_size = len(matching)
    elif punch_type == 'check_out' and pairs_list:
        matching = [inp for (inp, o) in pairs_list if _circular_dist(o, lone_min) <= WINDOW]
        if matching:
            corr_suggestion  = _fmt_hm(_circular_mean(matching))
            corr_sample_size = len(matching)

    return {
        'type':             punch_type,
        'confidence':       confidence,
        'avg_in':           _fmt_hm(avg_in),
        'avg_out':          _fmt_hm(avg_out),
        'corr_suggestion':  corr_suggestion,
        'corr_sample_size': corr_sample_size,
    }


def _fmt_hm(minutes: int) -> str:
    if minutes is None:
        return "—"
    hh = int(minutes) // 60
    mm = int(minutes) % 60
    return f"{hh:02d}:{mm:02d}"


def _to_12h(t24: str) -> str:
    m = to_minutes(t24)
    if m is None:
        return t24
    hh = (m // 60) % 24
    mn = m % 60
    period = "م" if hh >= 12 else "ص"
    h12    = hh % 12 or 12
    return f"{h12}:{mn:02d} {period}"


def _qtime_from_hhmm(t: str) -> QTime:
    m = to_minutes(t)
    if m is None:
        return QTime(8, 0)
    return QTime((m // 60) % 24, m % 60)


# ─── ReviewPanel Widget ────────────────────────────────────────────────────────

class ReviewPanel(QWidget):
    """
    يعرض قائمة البصمات الناقصة لموظف واحد.
    يُطلق change_confirmed(pending_key, pending_data) عند تأكيد تصحيح.
    """
    change_confirmed = Signal(str, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(8)
        self._empty_label = QLabel("✅ لا توجد بصمات تحتاج مراجعة")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(self._empty_label)

    # ══════════════════════════════════════════════════════════════════
    def rebuild(self, eid: str, days: list, corrections: dict,
                day_overrides: dict, pending: dict):
        """يُعيد بناء اللوحة بالكامل لموظف جديد أو بعد أي تعديل."""
        # حذف كل الـ Widgets القديمة
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # جمع البصمات غير المحلولة
        unresolved = []
        for di, d in enumerate(days):
            if not d.get('needs_review'):
                continue
            key_base = f"{eid}_{di}"
            if key_base in day_overrides:
                continue
            for ri, rev in enumerate(d['needs_review']):
                rev_key     = f"{key_base}_r{ri}"
                pending_key = f"corr_{key_base}_{ri}"
                if corrections.get(key_base, {}).get(rev_key):
                    continue
                if pending_key in pending:
                    continue
                unresolved.append((di, d, ri, rev, key_base, rev_key, pending_key))

        if not unresolved:
            lbl = QLabel("✅ لا توجد بصمات تحتاج مراجعة")
            lbl.setAlignment(Qt.AlignCenter)
            self._layout.addWidget(lbl)
            return

        for (di, d, ri, rev, key_base, rev_key, pending_key) in unresolved:
            card = self._build_review_card(
                eid, di, d, ri, rev, key_base, rev_key, pending_key, days
            )
            self._layout.addWidget(card)

        self._layout.addStretch()

    # ══════════════════════════════════════════════════════════════════
    def _build_review_card(self, eid, di, d, ri, rev,
                           key_base, rev_key, pending_key, all_days) -> QFrame:
        ci = rev.get('ci', '')
        clf = _classify_lone_punch(ci, all_days, shift_pattern=d.get('shift_pattern'))

        punch_type      = clf['type']
        confidence      = clf['confidence']
        corr_suggestion = clf['corr_suggestion']
        sample_size     = clf['corr_sample_size']

        card = QFrame()
        card.setStyleSheet(
            "QFrame { background:#efe9de; border:1px solid #e6dfd8; "
            "border-radius:8px; padding:4px; }"
        )
        layout = QVBoxLayout(card)
        layout.setSpacing(6)

        # ── العنوان ──
        title = QLabel(f"<b>يوم {d['day']}</b>")
        layout.addWidget(title)

        # ── وصف التشخيص ──
        if punch_type == 'check_in':
            conf_icon = "🟢" if confidence == 'high' else "🟡"
            desc = (f"⚠️ بصمة {_to_12h(ci)} — <b>حضور</b> على الأرجح {conf_icon} "
                    f"| لا يوجد انصراف مقابل")
        elif punch_type == 'check_out':
            conf_icon = "🟢" if confidence == 'high' else "🟡"
            desc = (f"⚠️ بصمة {_to_12h(ci)} — <b>انصراف</b> على الأرجح {conf_icon} "
                    f"| لا يوجد حضور مقابل")
        else:
            desc = (f"⚠️ بصمة {_to_12h(ci)} — لم يتمكن البرنامج من تحديد نوعها "
                    f"(بيانات غير كافية) — تحتاج مراجعة يدوية")
        desc_lbl = QLabel(desc)
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        # ── الاقتراح الذكي ──
        if corr_suggestion and punch_type in ('check_in', 'check_out') and sample_size > 0:
            if punch_type == 'check_in':
                sugg_txt = (f"💡 اقتراح ذكي: انصراف <b>{_to_12h(corr_suggestion)}</b> "
                            f"(من {sample_size} يوم مشابه)")
            else:
                sugg_txt = (f"💡 اقتراح ذكي: حضور <b>{_to_12h(corr_suggestion)}</b> "
                            f"(من {sample_size} يوم مشابه)")
            sugg_lbl = QLabel(sugg_txt)
            sugg_lbl.setStyleSheet("color:#2f6f63; font-size:12px;")
            layout.addWidget(sugg_lbl)

        # ── أدوات الإدخال ──
        input_row = QHBoxLayout()

        # Dropdown: اختيار ذكي أو يدوي
        combo = QComboBox()
        combo.addItem("لم يُحدَّد بعد")
        if corr_suggestion and punch_type in ('check_in', 'check_out'):
            combo.addItem(f"✨ الاقتراح الذكي ({_to_12h(corr_suggestion)})")
        combo.addItem("تحديد يدوي")
        input_row.addWidget(combo)

        # QTimeEdit للإدخال اليدوي
        time_edit = QTimeEdit()
        time_edit.setDisplayFormat("hh:mm")
        time_edit.setTime(QTime(8, 0))
        time_edit.setVisible(False)
        input_row.addWidget(time_edit)

        # تبديل ظهور QTimeEdit مع اختيار "يدوي"
        def _on_combo_changed(idx, te=time_edit, cb=combo):
            te.setVisible(cb.currentText() == "تحديد يدوي")

        combo.currentIndexChanged.connect(_on_combo_changed)
        layout.addLayout(input_row)

        # نوع الدور (حضور/انصراف)
        role_row = QHBoxLayout()
        role_lbl = QLabel("نوع البصمة:")
        role_combo = QComboBox()
        if punch_type == 'check_out':
            role_combo.addItems(["انصراف (الاقتراح)", "حضور (تبديل يدوي)"])
        else:
            role_combo.addItems(["حضور (الاقتراح)", "انصراف (تبديل يدوي)"])
        role_row.addWidget(role_lbl)
        role_row.addWidget(role_combo)
        role_row.addStretch()
        layout.addLayout(role_row)

        # ── زر التأكيد ──
        confirm_btn = QPushButton(f"✅ تأكيد تصحيح يوم {d['day']}")
        confirm_btn.setStyleSheet(
            "QPushButton { background:#cc785c; color:#fff; border-radius:6px; padding:6px 14px; }"
            "QPushButton:hover { background:#a9583e; }"
        )

        def _on_confirm(_c=False,
                        _combo=combo, _te=time_edit, _rc=role_combo,
                        _ci=ci, _pt=punch_type, _cs=corr_suggestion,
                        _pkey=pending_key, _kbase=key_base, _rkey=rev_key):
            sel = _combo.currentText()
            if sel == "لم يُحدَّد بعد":
                return

            if sel.startswith("✨") and _cs:
                chosen = _cs
            else:
                t = _te.time()
                chosen = f"{t.hour():02d}:{t.minute():02d}"

            # تحديد الدور الفعلي
            rc_text = _rc.currentText()
            if _pt == 'check_out':
                effective_role = 'check_in' if 'تبديل' in rc_text else 'check_out'
            else:
                effective_role = 'check_out' if 'تبديل' in rc_text else 'check_in'

            self.change_confirmed.emit(_pkey, {
                'type':       'correction',
                'key_base':   _kbase,
                'rev_key':    _rkey,
                'value':      chosen,
                'punch_role': effective_role,
            })

        confirm_btn.clicked.connect(_on_confirm)
        layout.addWidget(confirm_btn)

        return card
