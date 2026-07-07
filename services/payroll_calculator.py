# services/payroll_calculator.py
# منطق حساب الملخص اليومي/الشهري وكشف الرواتب.
#
# ⚠️ التزام صارم بمبدأ "لا تغيير منطقي" (claude.md §5): apply_early_tolerance
# منقولة هنا حرفيًا من oldapp.py بنفس المعادلات بالضبط. الدالتان الأخريان
# (summarize_emp_days و calculate_payroll) هما نفس منطق الجزء المكافئ من
# apply_overrides/calculate_payroll في oldapp.py، لكن summarize_emp_days
# لا تطبّق أي تصحيحات يدوية أو day_overrides عمدًا — دي هتُضاف في Phase 5
# عبر corrections_engine.py، طبقًا لتقسيم phases.md (Phase 4 صراحة: "بدون
# التصحيحات اليدوية بعد").

import pandas as pd


def to_minutes(t):
    t = str(t).strip()
    if not t:
        return None
    parts = t.split(':')
    try:
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        return None


def apply_early_tolerance(emp_days: dict, tolerance_minutes: int, tolerance_enabled: bool,
                          saturate_min: int | None = None) -> dict:
    """
    منقولة حرفيًا (نفس المعادلات) من oldapp.py — تعويض المغادرة المبكرة
    باستخدام حد الـ Saturate كمرجع ثابت. راجع التعليق التفصيلي الأصلي في
    oldapp.py لشرح كامل للمنطق.
    """
    if not tolerance_enabled or tolerance_minutes <= 0 or saturate_min is None or saturate_min <= 0:
        return emp_days

    sh = saturate_min // 60
    sm = saturate_min % 60
    saturate_time = f"{sh:02d}:{sm:02d}"
    tolerance = tolerance_minutes

    for eid, days in emp_days.items():
        for d in days:
            if d['status'] != 'حضور':
                continue
            raw_times = d.get('raw_times', [])
            if len(raw_times) < 2:
                continue

            actual_out_str = raw_times[-1]
            actual_out = to_minutes(actual_out_str)
            if actual_out is None:
                continue

            diff = (saturate_min - actual_out) % 1440
            if diff > 720:
                continue

            if 0 < diff <= tolerance:
                added_minutes = diff
                d['total_min'] += added_minutes
                d['tolerance_added'] = added_minutes
                d['raw_times'][-1] = saturate_time

                if d['punch_pairs']:
                    last_pair = d['punch_pairs'][-1]
                    pair_str, old_diff = last_pair
                    parts = pair_str.rstrip("✓").strip().split('→')
                    if len(parts) == 2:
                        suffix = "✓" if pair_str.endswith("✓") else ""
                        new_pair_str = f"{parts[0]}→{saturate_time}{suffix}"
                        new_diff = old_diff + added_minutes
                        d['punch_pairs'][-1] = (new_pair_str, new_diff)

    return emp_days


def summarize_emp_days(emp_days: dict) -> dict:
    """
    ملخص شهري لكل موظف (work_minutes, work_hours, attendance_days,
    absent_days, incomplete_days) بعد تطبيق apply_early_tolerance فقط —
    بدون أي تصحيحات يدوية أو day_overrides (Phase 5).

    هذا يقابل الجزء المكافئ بالضبط من حلقة apply_overrides في oldapp.py
    عندما لا توجد أي corrections أو day_overrides مسجّلة.
    """
    summary = {}
    for eid, days in emp_days.items():
        total_min = sum(d['total_min'] for d in days)
        att_days_cnt = sum(1 for d in days if d['status'] == 'حضور' and d['total_min'] > 0)
        absent_cnt = sum(1 for d in days if d['status'] == 'غياب')
        incomplete_cnt = sum(1 for d in days if d['incomplete'])
        summary[eid] = {
            'work_minutes': total_min,
            'work_hours': round(total_min / 60, 2),
            'attendance_days': att_days_cnt,
            'absent_days': absent_cnt,
            'incomplete_days': incomplete_cnt,
        }
    return summary


PAYROLL_COLUMNS = [
    'ID', 'الاسم', 'القسم', 'أيام الحضور', 'أيام الغياب',
    'أيام بصمة ناقصة', 'ساعات العمل الفعلية', 'سعر الساعة', 'صافي الراتب',
]


def calculate_payroll(df: pd.DataFrame, hourly_rates: dict, overrides_summary: dict) -> pd.DataFrame:
    """نفس معادلة calculate_payroll في oldapp.py حرفيًا — نفس أسماء الأعمدة بالعربي بالضبط."""
    rows = []
    for _, emp in df.iterrows():
        eid = str(emp['id'])
        rate = hourly_rates.get(eid, 0.0)
        if rate <= 0:
            continue
        ov = overrides_summary.get(eid, {})
        work_h = ov.get('work_hours', emp.get('work_hours', 0))
        att_days = ov.get('attendance_days', emp.get('attendance_days', 0))
        absent_days = ov.get('absent_days', emp.get('absent_days', 0))
        inc_days = ov.get('incomplete_days', emp.get('incomplete_days', 0))
        net = round(work_h * rate, 2)
        rows.append({
            'ID': eid,
            'الاسم': emp['name'],
            'القسم': emp.get('department', ''),
            'أيام الحضور': round(float(att_days), 1),
            'أيام الغياب': int(absent_days),
            'أيام بصمة ناقصة': int(inc_days),
            'ساعات العمل الفعلية': round(work_h, 2),
            'سعر الساعة': rate,
            'صافي الراتب': net,
        })
    return pd.DataFrame(rows, columns=PAYROLL_COLUMNS)
