# services/parsers/hikvision_parser.py
# ============================================================
# Parser لملفات HikVision (ورقة AttendanceRecord)
# منقول حرفيًا من parse_file_hikvision في oldapp.py — بدون أي تغيير منطقي.
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


def parse_file_hikvision(file_bytes, cutoff_hour: float = 3.0, saturate_min: int = None,
                          duplicate_punch_tolerance: int = 10):
    """
    يقرأ ملف HikVision بتنسيق AttendanceRecord.
    الهيكل:
      - ورقة واحدة اسمها 'AttendanceRecord'
      - صف 3 (index): Employee ID | Card No. | Name | Department | 2025/06/01 | 2025/06/02 | ...
      - صف 4: '' | '' | '' | '' | SW - EW | SW - EW | ...
      - صفوف 5+: كل صف = موظف واحد
      - كل خلية يوم = 4 أسطر مفصولة بـ \\n، كل سطر = "HH:MM HH:MM"
        حيث --:-- = لا يوجد بصمة
    يضمن:
      - أي عدد أيام (28/29/30/31 أو نص شهر) ← ديناميكي من headers
      - بصمة في موضع الحضور فقط  → needs_review
      - بصمة في موضع الانصراف فقط (--:-- HH:MM) → needs_review
      - كلا البصمتين موجودتان → زوج مكتمل

    Returns:
        (summary_df: pd.DataFrame, emp_days: dict)
    """
    wb = xlrd.open_workbook(file_contents=file_bytes)
    sh = wb.sheet_by_name('AttendanceRecord')

    # ── بناء خريطة عمود → رقم اليوم (ديناميكي) ──────────────────────────
    col_to_day = {}
    for c in range(sh.ncols):
        header = str(sh.cell_value(3, c)).strip()   # مثال: '2025/06/15'
        if '/' in header:
            try:
                day_num = int(header.split('/')[-1])  # آخر جزء = اليوم
                col_to_day[c] = day_num
            except (ValueError, IndexError):
                pass

    raw_punches = {}
    log_names = {}
    log_depts = {}

    # ── قراءة بيانات الموظفين (من صف 5 وما بعده) ─────────────────────────
    for r in range(5, sh.nrows):
        eid = str(sh.cell_value(r, 0)).strip()
        name = str(sh.cell_value(r, 2)).strip()
        dept = str(sh.cell_value(r, 3)).strip()

        if not eid or not name:
            continue
        # تحويل eid لرقم صحيح إن أمكن (يزيل .0 من الأرقام)
        try:
            eid = str(int(float(eid)))
        except (ValueError, TypeError):
            pass

        log_names[eid] = name
        log_depts[eid] = dept

        punches = {}
        for c, day_num in col_to_day.items():
            cell_val = str(sh.cell_value(r, c)).strip()
            if not cell_val:
                continue

            # كل سطر = جلسة واحدة: "HH:MM HH:MM" أو "--:-- HH:MM" إلخ
            day_times = []
            for line in cell_val.split('\n'):
                parts = line.strip().split()
                for p in parts:
                    if re.match(r'^\d{1,2}:\d{2}$', p):
                        day_times.append(('real', p))
                    elif p == '--:--':
                        day_times.append(('empty', p))

            # نعالج الجلسات: كل سطر = زوج (حضور, انصراف)
            real_times = []
            i = 0
            while i + 1 < len(day_times):
                t_in_type, t_in = day_times[i]
                t_out_type, t_out = day_times[i + 1]
                i += 2

                has_in = (t_in_type == 'real')
                has_out = (t_out_type == 'real')

                if has_in and has_out:
                    real_times.extend([t_in, t_out])
                elif has_in and not has_out:
                    real_times.append(t_in)
                elif not has_in and has_out:
                    real_times.append(t_out)
                # كلاهما فارغ → تجاهل

            if real_times:
                # حذف البصمات المتقاربة
                real_times = remove_close_punches(real_times, tolerance_minutes=duplicate_punch_tolerance)
                punches[day_num] = real_times

        raw_punches[eid] = punches

    # ── ضمان وجود كل أيام الشهر قبل Redistribute ──────────────────────────
    _all_known_days = set(col_to_day.values())
    for _eid in raw_punches:
        for _day in _all_known_days:
            raw_punches[_eid].setdefault(_day, [])

    # ── تطبيق Redistribute ────────────────────────────────────────────────
    raw_punches = redistribute_overnight_punches(raw_punches, cutoff_hour=cutoff_hour)

    # ── تطبيق Saturate ────────────────────────────────────────────────────
    if saturate_min is not None and saturate_min > 0:
        raw_punches = saturate_punches(raw_punches, saturate_min=saturate_min)

    # ── بناء emp_days (نفس هيكل parse_file القديم تماماً) ─────────────────
    # HikVision لا يوفر معلومات الغياب/العطل في الملف → نعتمد على البصمات فقط
    emp_days = {}

    for eid, punches in raw_punches.items():
        all_days = set(col_to_day.values()) | set(punches.keys())
        days = []

        for day_num in sorted(all_days):
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

            # HikVision: لو فيه بصمات = حضور، لو مفيش = غياب
            if times:
                status = 'حضور'
            else:
                status = 'غياب'

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
