# services/parsers/zk_classic_parser.py
# ============================================================
# Parser للصيغة القديمة (Att.log report) — أجهزة ZK Classic
# منقول حرفيًا من parse_file في oldapp.py — بدون أي تغيير منطقي.
# ============================================================
# ⚠️ ممنوع تعديل أي منطق هنا إلا بعد اجتياز اختبارات Regression
# (راجع phases.md — Phase 2: "لا تنتقل لمرحلة تالية قبل اجتياز هذه الاختبارات 100%")
#
# [تصحيح] build_summary_rows بترجع list[dict] — لازم تتحول لـ pd.DataFrame
# هنا عشان باقي الكود (main_window.py, dashboard_view.py, payroll_calculator.py)
# مبني على افتراض إنها DataFrame (زي oldapp.py الأصلي بالظبط).

import re
import xlrd
import pandas as pd

from services.parsers.common import (
    remove_close_punches,
    minutes_diff,
    redistribute_overnight_punches,
    saturate_punches,
    assign_shift_patterns,
    build_summary_rows,
)


def parse_file(file_bytes, cutoff_hour: float = 3.0, saturate_min: int = None,
               duplicate_punch_tolerance: int = 10):
    """
    يقرأ ملف الصيغة القديمة (Att.log report) القادم من جهاز ZK Classic.

    Returns:
        (summary_df: pd.DataFrame, emp_days: dict)
    """
    wb = xlrd.open_workbook(file_contents=file_bytes)

    log_sh = wb.sheet_by_name('Att.log report')

    col_to_day = {}
    for c in range(log_sh.ncols):
        v = str(log_sh.cell_value(3, c)).strip()
        if v:
            try:
                col_to_day[c] = int(float(v))
            except (ValueError, TypeError):
                pass

    raw_punches = {}
    log_names = {}
    log_depts = {}

    for r in range(log_sh.nrows):
        if str(log_sh.cell_value(r, 0)).strip() != 'ID:':
            continue
        eid = str(log_sh.cell_value(r, 2)).strip()
        name = str(log_sh.cell_value(r, 10)).strip()
        dept = str(log_sh.cell_value(r, 20)).strip()
        log_names[eid] = name
        log_depts[eid] = dept

        punch_row = r + 1
        if punch_row >= log_sh.nrows:
            continue
        punches = {}
        for c, day in col_to_day.items():
            if c >= log_sh.ncols:
                continue
            v = str(log_sh.cell_value(punch_row, c)).strip()
            if v:
                times = re.findall(r'\d{1,2}:\d{2}', v)
                if times:
                    # حذف البصمات المتقاربة جداً
                    times = remove_close_punches(times, tolerance_minutes=duplicate_punch_tolerance)
                    punches[day] = times
        raw_punches[eid] = punches

    # ── ضمان وجود كل أيام الشهر قبل Redistribute ──────────────────────────
    _all_known_days = set(col_to_day.values())
    for _eid in raw_punches:
        for _day in _all_known_days:
            raw_punches[_eid].setdefault(_day, [])

    raw_punches = redistribute_overnight_punches(raw_punches, cutoff_hour=cutoff_hour)

    # ── تطبيق Saturate بعد Redistribute ──────────────────────────────────
    if saturate_min is not None and saturate_min > 0:
        raw_punches = saturate_punches(raw_punches, saturate_min=saturate_min)

    skip = {'Schedule Infor.', 'Att. Stat.', 'Att.log report', 'Exception Stat.'}
    absent_info = {}

    for sname in wb.sheet_names():
        if sname in skip:
            continue
        sh = wb.sheet_by_name(sname)
        for offset in [0, 15, 30]:
            name_col = offset + 9
            if name_col >= sh.ncols:
                continue
            eid = str(sh.cell_value(3, name_col)).strip()
            if not eid or eid == 'ID':
                continue
            day_status = {}
            for r in range(11, min(41, sh.nrows)):
                day_label = str(sh.cell_value(r, offset + 0)).strip()
                if not day_label:
                    continue
                m = re.match(r'^(\d+)', day_label)
                if not m:
                    continue
                day_num = int(m.group(1))
                on1 = str(sh.cell_value(r, offset + 1)).strip()
                has_any = any(
                    str(sh.cell_value(r, offset + c)).strip()
                    for c in [1, 3, 6, 8, 10, 12]
                    if offset + c < sh.ncols
                )
                if on1 == 'Absent':
                    day_status[day_num] = 'absent'
                elif not has_any:
                    day_status[day_num] = 'weekend'
            absent_info[eid] = day_status

    emp_days = {}

    for eid, punches in raw_punches.items():
        all_days = set(absent_info.get(eid, {}).keys()) | set(punches.keys())
        days = []

        for day_num in sorted(all_days):
            status_marker = absent_info.get(eid, {}).get(day_num, 'present')
            times = punches.get(day_num, [])

            pairs = []
            for i in range(0, len(times) - 1, 2):
                diff = minutes_diff(times[i], times[i + 1])
                if diff is not None:
                    pairs.append((f"{times[i]}→{times[i+1]}", diff))

            has_unpaired = (len(times) % 2 == 1)
            unpaired_time = times[-1] if has_unpaired else None

            total_min = sum(m for _, m in pairs)
            incomplete = has_unpaired

            needs_review = []
            if has_unpaired:
                needs_review.append({
                    'type': 'missing_out',
                    'ci': unpaired_time,
                    'co': None,
                    'resolved': False,
                    'resolved_co': None,
                    'suggested': None,
                })

            if status_marker == 'absent' or (status_marker == 'weekend' and not times):
                status = 'غياب'
            else:
                status = 'حضور'

            days.append({
                'day': f"{day_num:02d}",
                'status': status,
                'total_min': total_min,
                'incomplete': incomplete,
                'punch_pairs': pairs,
                'needs_review': needs_review,
                'raw_times': times,
                'tolerance_added': 0,
            })

        emp_days[eid] = days

    # تعيين أنماط الدوام
    assign_shift_patterns(emp_days)

    summary_rows = build_summary_rows(emp_days, log_names, log_depts)
    return pd.DataFrame(summary_rows), emp_days
