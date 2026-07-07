# services/parsers/common.py
# ============================================================
# دوال مساعدة مشتركة بين كل الـ Parsers — منقولة حرفيًا من oldapp.py
# ============================================================
# ⚠️ قاعدة صارمة (راجع claude.md وphases.md):
# أي تعديل في هذا الملف قد يغيّر نتيجة حساب ساعات/رواتب موظف حقيقي.
# ممنوع تغيير أي منطق هنا إلا بعد اجتياز اختبارات Regression في tests/test_parsers.py

import math


# نافذة "ما بعد منتصف الليل" المشتركة (من 12:00 ص إلى 6:00 ص) — بالدقائق.
OVERNIGHT_WINDOW_MAX = 360  # 6:00 ص


def remove_close_punches(times_list: list, tolerance_minutes: int = 10) -> list:
    """حذف البصمات المتقاربة جداً من بعضها."""
    if not times_list or len(times_list) <= 1:
        return times_list

    filtered = [times_list[0]]

    for current_time_str in times_list[1:]:
        try:
            last_time = filtered[-1]
            last_h, last_m = map(int, last_time.split(':'))
            curr_h, curr_m = map(int, current_time_str.split(':'))

            last_total_min = last_h * 60 + last_m
            curr_total_min = curr_h * 60 + curr_m

            diff = abs(curr_total_min - last_total_min)

            if diff > tolerance_minutes:
                filtered.append(current_time_str)
        except (ValueError, IndexError):
            filtered.append(current_time_str)

    return filtered


def to_minutes(t):
    t = str(t).strip()
    if not t:
        return None
    parts = t.split(':')
    try:
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        return None


def minutes_diff(t_in, t_out):
    m_in = to_minutes(t_in)
    m_out = to_minutes(t_out)
    if m_in is None or m_out is None:
        return None
    diff = m_out - m_in
    if diff < 0:
        diff += 24 * 60
    return diff


def fmt_hm(minutes):
    if minutes is None or minutes == 0:
        return "0:00"
    hh = int(minutes) // 60
    mm = int(minutes) % 60
    return f"{hh}:{mm:02d}"


def fmt_h(hours):
    if hours is None or hours == 0:
        return "0:00"
    return fmt_hm(round(hours * 60))


def fmt_days(n):
    if n is None:
        return "0"
    n = float(n)
    if n.is_integer():
        return str(int(n))
    return f"{n:.1f}"


def to_12h(t24: str) -> str:
    m = to_minutes(t24)
    if m is None:
        return t24
    hh = (m // 60) % 24
    mm = m % 60
    period = "م" if hh >= 12 else "ص"
    h12 = hh % 12 or 12
    return f"{h12}:{mm:02d} {period}"


def from_12h(h: int, mn: int, period: str) -> str:
    h = int(h)
    mn = int(mn)
    if period == "ص":
        hh24 = 0 if h == 12 else h
    else:
        hh24 = 12 if h == 12 else h + 12
    return f"{hh24:02d}:{mn:02d}"


def circular_mean(minutes_list: list) -> int:
    """
    حساب المتوسط الدائري لقائمة أوقات (بالدقائق) بحيث يعمل بشكل صحيح
    مع بصمات ما بعد منتصف الليل.
    """
    if not minutes_list:
        return 0
    n = len(minutes_list)
    sin_sum = sum(math.sin(2 * math.pi * m / 1440) for m in minutes_list)
    cos_sum = sum(math.cos(2 * math.pi * m / 1440) for m in minutes_list)
    angle = math.atan2(sin_sum / n, cos_sum / n)
    result = round(angle * 1440 / (2 * math.pi)) % 1440
    return int(result)


def circular_dist(a: int, b: int) -> int:
    """المسافة الدائرية بين وقتين بالدقائق (تأخذ بعين الاعتبار تجاوز منتصف الليل)."""
    d = abs(a - b)
    return min(d, 1440 - d)


# ════════════════════════ نظام الأنماط (Shift Patterns) ════════════════════════

def cluster_times_circular(times_in_minutes, min_gap_minutes=120):
    """
    يقسم قائمة أوقات (بالدقائق) إلى مجموعات تمثل أنماط دوام مختلفة.
    """
    if not times_in_minutes:
        return []
    sorted_times = sorted(times_in_minutes)
    n = len(sorted_times)
    if n <= 1:
        return [sorted_times]

    gaps = []
    for i in range(n):
        t1 = sorted_times[i]
        t2 = sorted_times[(i + 1) % n]
        diff = (t2 - t1) % 1440
        gaps.append((diff, i))

    start_indices = []
    _, max_gap_idx = max(gaps, key=lambda x: x[0])
    current_idx = (max_gap_idx + 1) % n
    cluster = []
    for _ in range(n):
        t = sorted_times[current_idx]
        if cluster:
            last_t = cluster[-1]
            gap = (t - last_t) % 1440
            if gap >= min_gap_minutes:
                start_indices.append(current_idx)
        cluster.append(t)
        current_idx = (current_idx + 1) % n
        if current_idx == (max_gap_idx + 1) % n:
            break

    if not start_indices:
        return [sorted_times]

    clusters = []
    start = 0
    for idx in start_indices:
        clusters.append(sorted_times[start:idx])
        start = idx
    clusters.append(sorted_times[start:])
    clusters = [c for c in clusters if c]
    return clusters


def assign_shift_patterns(emp_days):
    """
    يحلل أيام كل موظف ويعين نمط دوام لكل يوم بناءً على وقت الحضور.
    يضيف مفتاح 'shift_pattern' (int) لكل يوم في emp_days.
    """
    for eid, days in emp_days.items():
        in_times = []
        valid_days_indices = []
        for di, d in enumerate(days):
            if d['raw_times'] and len(d['raw_times']) >= 2:
                in_m = to_minutes(d['raw_times'][0])
                if in_m is not None:
                    in_times.append(in_m)
                    valid_days_indices.append(di)

        if not in_times:
            for d in days:
                d['shift_pattern'] = None
            continue

        clusters = cluster_times_circular(in_times, min_gap_minutes=120)
        pattern_centers = []
        for cl in clusters:
            center = circular_mean(cl)
            pattern_centers.append(center)

        for di, d in enumerate(days):
            times = d.get('raw_times', [])
            if not times:
                d['shift_pattern'] = None
                continue
            first_time_min = to_minutes(times[0])
            if first_time_min is None:
                d['shift_pattern'] = None
                continue

            min_dist = float('inf')
            assigned_pattern = None
            for p_idx, center in enumerate(pattern_centers):
                dist = circular_dist(first_time_min, center)
                if dist < min_dist:
                    min_dist = dist
                    assigned_pattern = p_idx
            d['shift_pattern'] = assigned_pattern


def classify_lone_punch(lone_time: str, all_days: list, shift_pattern=None) -> dict:
    """
    يحدد هل البصمة الوحيدة في اليوم هي حضور أم انصراف.
    إذا تم توفير shift_pattern (رقم)، يتم فقط استخدام الأيام التي تنتمي لنفس النمط.
    """
    lone_min = to_minutes(lone_time)
    if lone_min is None:
        return {'type': 'unknown', 'confidence': 'low', 'avg_in': None, 'avg_out': None,
                'dist_to_in': None, 'dist_to_out': None,
                'corr_suggestion': None, 'corr_sample_size': 0}

    if shift_pattern is not None:
        relevant_days = [d for d in all_days if d.get('shift_pattern') == shift_pattern]
    else:
        relevant_days = all_days

    check_in_mins = []
    check_out_mins = []
    pairs_list = []

    for d in relevant_days:
        times = d.get('raw_times', [])
        if len(times) >= 2:
            first_min = to_minutes(times[0])
            last_min = to_minutes(times[-1])
            if first_min is not None:
                check_in_mins.append(first_min)
            if last_min is not None:
                check_out_mins.append(last_min)
            for i in range(0, len(times) - 1, 2):
                in_m = to_minutes(times[i])
                out_m = to_minutes(times[i + 1])
                if in_m is not None and out_m is not None:
                    raw_diff = out_m - in_m
                    if raw_diff < 0:
                        raw_diff += 1440
                    if 2 <= raw_diff <= 960:
                        pairs_list.append((in_m, out_m))

    if not check_in_mins or not check_out_mins:
        if shift_pattern is not None:
            return classify_lone_punch(lone_time, all_days, shift_pattern=None)
        return {'type': 'unknown', 'confidence': 'low', 'avg_in': None, 'avg_out': None,
                'dist_to_in': None, 'dist_to_out': None,
                'corr_suggestion': None, 'corr_sample_size': 0}

    avg_in = circular_mean(check_in_mins)
    avg_out = circular_mean(check_out_mins)

    dist_in = circular_dist(lone_min, avg_in)
    dist_out = circular_dist(lone_min, avg_out)

    avg_in_str = fmt_hm(avg_in)
    avg_out_str = fmt_hm(avg_out)

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
    corr_suggestion = None
    corr_sample_size = 0

    if punch_type == 'check_in' and pairs_list:
        matching_outs = [
            out for (inp, out) in pairs_list
            if circular_dist(inp, lone_min) <= WINDOW
        ]
        if matching_outs:
            corr_suggestion = fmt_hm(circular_mean(matching_outs))
            corr_sample_size = len(matching_outs)

    elif punch_type == 'check_out' and pairs_list:
        matching_ins = [
            inp for (inp, out) in pairs_list
            if circular_dist(out, lone_min) <= WINDOW
        ]
        if matching_ins:
            corr_suggestion = fmt_hm(circular_mean(matching_ins))
            corr_sample_size = len(matching_ins)

    return {
        'type': punch_type,
        'confidence': confidence,
        'avg_in': avg_in_str,
        'avg_out': avg_out_str,
        'dist_to_in': dist_in,
        'dist_to_out': dist_out,
        'corr_suggestion': corr_suggestion,
        'corr_sample_size': corr_sample_size,
    }


# ════════════════════════ Redistribute / Saturate ════════════════════════

def redistribute_overnight_punches(raw_punches: dict, cutoff_hour: float = 3.0) -> dict:
    cutoff_min = int(cutoff_hour * 60)
    result = {eid: {day: list(times) for day, times in days.items()}
              for eid, days in raw_punches.items()}

    for eid, days in result.items():
        sorted_days = sorted(days.keys())
        for i, day in enumerate(sorted_days):
            times = days[day]
            if not times:
                continue

            overnight = []
            remaining = []
            for t in times:
                m = to_minutes(t)
                if m is not None and m < cutoff_min:
                    overnight.append(t)
                else:
                    remaining.append(t)

            if not overnight:
                continue

            if i > 0:
                prev_day = sorted_days[i - 1]
                days[prev_day] = days[prev_day] + overnight
            days[day] = remaining

    return result


def saturate_punches(raw_punches: dict, saturate_min: int,
                      window_max: int = OVERNIGHT_WINDOW_MAX) -> dict:
    """
    دالة مستقلة تمامًا عن حد الـ Redistribute (cutoff) — وتُطبَّق فقط على
    آخر بصمة في قائمة اليوم (الانصراف)، وليس على بصمة الحضور (الأولى)
    أو أي بصمة وسطى.
    """
    sh = saturate_min // 60
    sm = saturate_min % 60
    cap = f"{sh:02d}:{sm:02d}"

    result = {}
    for eid, days in raw_punches.items():
        result[eid] = {}
        for day, times in days.items():
            if not times:
                result[eid][day] = times
                continue

            new_times = list(times)
            m = to_minutes(new_times[-1])
            if m is not None and saturate_min < m <= window_max:
                new_times[-1] = cap

            result[eid][day] = new_times
    return result


def build_summary_rows(emp_days, log_names, log_depts):
    """
    دالة مشتركة: تحوّل emp_days إلى قائمة صفوف ملخّص للموظفين (list[dict]).
    نفس _build_summary_df القديمة لكن بدون اعتمادية pandas مباشرة.
    """
    rows = []
    for eid, days in emp_days.items():
        total_min = sum(d['total_min'] for d in days)
        att_days_cnt = sum(1 for d in days if d['status'] == 'حضور' and d['total_min'] > 0)
        absent_cnt = sum(1 for d in days if d['status'] == 'غياب')
        incomplete_cnt = sum(1 for d in days if d['incomplete'])
        rows.append({
            'id': eid,
            'name': log_names.get(eid, eid),
            'department': log_depts.get(eid, ''),
            'work_minutes': total_min,
            'work_hours': round(total_min / 60, 2),
            'attendance_days': att_days_cnt,
            'absent_days': absent_cnt,
            'incomplete_days': incomplete_cnt,
        })
    return rows
