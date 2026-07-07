# services/corrections_engine.py
# منطق apply_overrides وكل الدوال المساعدة المرتبطة بها —
# منقولة حرفيًا من oldapp.py بدون أي تغيير في المنطق.
# الواجهة (UI) لا تعرف كيف يتم الحساب — تستدعي فقط apply_overrides.

import math

from services.parsers.common import classify_lone_punch


# ─── دوال مساعدة (مشتركة مع common.py لكن مُكررة هنا لاستقلالية الموديل) ───

def to_minutes(t) -> int | None:
    t = str(t).strip()
    if not t:
        return None
    parts = t.split(':')
    try:
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        return None


def minutes_diff(t_in, t_out) -> int | None:
    m_in  = to_minutes(t_in)
    m_out = to_minutes(t_out)
    if m_in is None or m_out is None:
        return None
    diff = m_out - m_in
    if diff < 0:
        diff += 24 * 60
    return diff


def fmt_hm(minutes) -> str:
    if minutes is None or minutes == 0:
        return "0:00"
    hh = int(minutes) // 60
    mm = int(minutes) % 60
    return f"{hh}:{mm:02d}"


def fmt_h(hours) -> str:
    if hours is None or hours == 0:
        return "0:00"
    return fmt_hm(round(hours * 60))


# ─── apply_early_tolerance ────────────────────────────────────────────────────
# (هنا نسخة مكررة طفيفة — الأصل في services/payroll_calculator.py —
#  للحفاظ على استقلالية corrections_engine تمامًا عن باقي الموديلات.)

def _apply_early_tolerance(emp_days: dict, tolerance_minutes: int,
                            tolerance_enabled: bool, saturate_min: int | None) -> dict:
    """نسخة داخلية تُستخدم فقط داخل apply_overrides."""
    if not tolerance_enabled or tolerance_minutes <= 0 or not saturate_min:
        return emp_days

    sh = saturate_min // 60
    sm = saturate_min % 60
    saturate_time = f"{sh:02d}:{sm:02d}"

    for eid, days in emp_days.items():
        for d in days:
            if d['status'] != 'حضور':
                continue
            raw_times = d.get('raw_times', [])
            if len(raw_times) < 2:
                continue
            actual_out = to_minutes(raw_times[-1])
            if actual_out is None:
                continue
            diff = (saturate_min - actual_out) % 1440
            if diff > 720:
                continue
            if 0 < diff <= tolerance_minutes:
                d['total_min'] = d.get('total_min', 0) + diff
                d['tolerance_added'] = diff
                d['raw_times'][-1] = saturate_time
                if d['punch_pairs']:
                    last_pair = d['punch_pairs'][-1]
                    pair_str, old_diff = last_pair
                    parts = pair_str.rstrip("✓").strip().split('→')
                    if len(parts) == 2:
                        suffix = "✓" if pair_str.endswith("✓") else ""
                        new_pair_str = f"{parts[0]}→{saturate_time}{suffix}"
                        d['punch_pairs'][-1] = (new_pair_str, old_diff + diff)
    return emp_days


# ─── apply_overrides ─────────────────────────────────────────────────────────

def apply_overrides(emp_days: dict,
                    corrections: dict,
                    day_overrides: dict,
                    pending: dict | None = None,
                    tolerance_enabled: bool = False,
                    tolerance_minutes: int = 0,
                    saturate_min: int | None = None) -> dict:
    """
    يحسب ملخص الساعات/الأيام لكل موظف مع الأخذ بعين الاعتبار:
      - التصحيحات اليدوية (corrections)
      - استبدالات الأيام الكاملة (day_overrides)
      - التعديلات المعلَّقة (pending) — اختياري
      - نظام التسامح مع المغادرة المبكرة — اختياري

    يُرجع dict: { eid: { work_minutes, work_hours, attendance_days, absent_days, incomplete_days } }
    """
    pending = pending or {}

    # دمج التعديلات المعلَّقة مع التصحيحات/الـ Overrides الحالية (نسخ محلية)
    effective_corrections   = {k: dict(v) for k, v in corrections.items()}
    effective_day_overrides = dict(day_overrides)

    for pv in pending.values():
        ptype = pv.get('type')
        if ptype == 'correction':
            kb = pv['key_base']
            effective_corrections.setdefault(kb, {})
            effective_corrections[kb][pv['rev_key']] = pv['value']
            effective_corrections[kb][f"{pv['rev_key']}_role"] = pv.get('punch_role', 'check_in')
        elif ptype == 'day_override':
            effective_day_overrides[pv['key_base']] = pv['data']
        elif ptype == 'remove_override':
            effective_day_overrides.pop(pv['key_base'], None)

    # تطبيق التسامح إن طُلب
    if tolerance_enabled and tolerance_minutes > 0 and saturate_min:
        emp_days = _apply_early_tolerance(emp_days, tolerance_minutes, tolerance_enabled, saturate_min)

    summary = {}

    for eid, days in emp_days.items():
        total_min       = 0
        att_days_cnt    = 0.0
        absent_days_cnt = 0
        incomplete_cnt  = 0

        for di, d in enumerate(days):
            key_base = f"{eid}_{di}"

            # ── Day Override له أولوية قصوى ──────────────────────────
            if key_base in effective_day_overrides:
                ov_day = effective_day_overrides[key_base]
                status = ov_day.get('status', 'غياب')
                pairs  = ov_day.get('pairs') or []
                day_total = 0
                for ci, co in pairs:
                    diff = minutes_diff(ci, co)
                    if diff is not None:
                        day_total += diff
                total_min += day_total
                if status == 'حضور':
                    att_days_cnt += 1
                elif status == 'غياب':
                    absent_days_cnt += 1
                continue

            # ── حساب تلقائي مع تصحيحات ────────────────────────────────
            day_corrections = effective_corrections.get(key_base, {})
            base_min  = sum(m for _, m in d.get('punch_pairs', []))
            extra_min = 0
            still_inc = False

            for ri, rev in enumerate(d.get('needs_review', [])):
                rev_key       = f"{key_base}_r{ri}"
                resolved_time = day_corrections.get(rev_key)
                if resolved_time:
                    punch_role = day_corrections.get(f"{rev_key}_role", 'check_in')
                    if punch_role == 'check_out':
                        diff = minutes_diff(resolved_time, rev['ci'])
                    else:
                        diff = minutes_diff(rev['ci'], resolved_time)
                    if diff is not None:
                        extra_min += diff
                else:
                    still_inc = True

            day_total  = base_min + extra_min
            total_min += day_total

            effective_status = d['status']
            if effective_status == 'غياب' and day_total > 0:
                effective_status = 'حضور'

            if effective_status == 'حضور' and (day_total > 0 or not still_inc):
                att_days_cnt += 1
            if effective_status == 'غياب':
                absent_days_cnt += 1
            if still_inc and d.get('incomplete', False):
                incomplete_cnt += 1

        summary[eid] = {
            'work_minutes':    total_min,
            'work_hours':      round(total_min / 60, 2),
            'attendance_days': att_days_cnt,
            'absent_days':     absent_days_cnt,
            'incomplete_days': incomplete_cnt,
        }

    return summary


# ─── Bulk Smart Apply (كل الموظفين) ──────────────────────────────────────────
# منقولة حرفيًا من oldapp.py (has_chronological_conflict سطر 3673،
# bulk_smart_apply_all سطر 3729) — التغيير الوحيد: الأصل كان بيقرأ/يكتب
# corrections/pending/day_overrides من st.session_state مباشرة (Streamlit)،
# هنا بقت معاملات صريحة، وبدل استدعاء add_pending_change() مباشرة (غير موجودة
# في هذا الموديل) بترجع الاقتراحات المعلَّقة كـ dict عشان الـ UI (PySide6) يدمجها
# في نظام الـ Pending Changes بتاعه بنفسه. **منطق القرار نفسه لم يتغيّر إطلاقًا.**

def has_chronological_conflict(d: dict, punch_type: str, corr_suggestion) -> bool:
    """
    فحص "زيرو تسامح": يتأكد إن الاقتراح الذكي لا يكسر الترتيب الزمني الفعلي
    لبصمات نفس اليوم قبل ما يُطبَّق تلقائيًا في bulk_smart_apply_all.

    البصمة الناقصة (لسه من غير زوج) هي دائمًا آخر عنصر في raw_times.
    بنقارن:
      1) البصمة الناقصة نفسها لازم تكون بعد الجار السابق ليها (آخر بصمة قبلها).
      2) الاقتراح المحسوب لازم يحافظ على نفس الترتيب:
         - لو النوع check_in  → الاقتراح (انصراف) لازم يكون بعد البصمة الناقصة.
         - لو النوع check_out → الاقتراح (حضور) لازم يكون بعد الجار السابق وقبل البصمة الناقصة.

    ترجع True لو فيه تعارض (يعني نرفض الاقتراح)، وFalse لو كل حاجة متسقة.
    """
    raw_times = d.get('raw_times', [])
    if len(raw_times) < 1:
        return True  # مفيش بيانات كافية أصلاً

    lone_min = to_minutes(raw_times[-1])
    if lone_min is None:
        return True

    prev_min = to_minutes(raw_times[-2]) if len(raw_times) >= 2 else None

    # 1) البصمة الناقصة نفسها لازم تيجي بعد الجار السابق مباشرة
    if prev_min is not None and lone_min <= prev_min:
        return True

    if not corr_suggestion:
        return False  # مفيش اقتراح أصلاً هيتفحص - القرار في مكان تاني

    corr_min = to_minutes(corr_suggestion)
    if corr_min is None:
        return True

    if punch_type == 'check_in':
        # الاقتراح = وقت انصراف، لازم بعد البصمة الناقصة (بسماح عبور منتصف الليل)
        diff = corr_min - lone_min
        if diff < 0:
            diff += 1440
        if not (0 < diff <= 960):
            return True

    elif punch_type == 'check_out':
        # الاقتراح = وقت حضور، لازم بعد الجار السابق وقبل البصمة الناقصة
        if prev_min is not None and not (prev_min < corr_min < lone_min):
            return True
        if prev_min is None and not (corr_min < lone_min):
            return True

    else:
        return True  # نوع غير معروف - رفض احتياطي

    return False


def bulk_smart_apply_all(emp_days: dict,
                          corrections: dict,
                          pending: dict,
                          day_overrides: dict,
                          min_sample: int = 3) -> dict:
    """
    يجمع كل البصمات الناقصة لكل الموظفين ويقترح تطبيق تلقائي فقط إذا:
      - confidence == 'high'
      - corr_sample_size >= min_sample
      - لم تُحلَّ بعد (لا في corrections ولا في pending ولا في day_overrides)
      - لا يوجد تعارض في الترتيب الزمني (has_chronological_conflict)

    ⚠️ هذه الدالة معاينة فقط (Preview) — لا تعدّل corrections/pending/day_overrides
    الممرَّرة لها. المُستدعي (UI) هو المسؤول عن دمج 'pending_changes' الراجعة
    داخل نظام الـ Pending Changes الخاص به بعد تأكيد المستخدم (زر "تطبيق").

    يُرجع dict:
      'applied':         list[dict]  (البصمات اللي هيتم اقتراح تطبيقها لو أكّد المستخدم)
      'skipped':         list[dict]  (البصمات اللي اتركت ولماذا)
      'pending_changes':  dict        ({pending_key: correction_payload} — جاهزة للدمج)
    """
    applied = []
    skipped = []
    proposed_pending = {}

    for eid, days in emp_days.items():
        for di, d in enumerate(days):
            if not d.get('needs_review'):
                continue
            key_base = f"{eid}_{di}"
            if key_base in day_overrides:
                continue
            for ri, rev in enumerate(d['needs_review']):
                rev_key     = f"{key_base}_r{ri}"
                pending_key = f"corr_{key_base}_{ri}"

                # تخطّي المحلولة مسبقاً
                if corrections.get(key_base, {}).get(rev_key):
                    continue
                if pending_key in pending:
                    continue

                ci  = rev.get('ci', '')
                sp  = d.get('shift_pattern')
                clf = classify_lone_punch(ci, days, shift_pattern=sp)

                punch_type       = clf['type']
                confidence       = clf['confidence']
                corr_suggestion  = clf['corr_suggestion']
                corr_sample_size = clf['corr_sample_size']

                info_base = {
                    'eid':      eid,
                    'day':      d['day'],
                    'ci':       ci,
                    'type':     punch_type,
                    'conf':     confidence,
                    'sample':   corr_sample_size,
                    'suggest':  corr_suggestion,
                }

                # شروط التطبيق الآمن
                if punch_type not in ('check_in', 'check_out'):
                    skipped.append({**info_base, 'reason': 'نوع غير معروف'})
                    continue
                if confidence != 'high':
                    skipped.append({**info_base, 'reason': 'ثقة منخفضة 🟡'})
                    continue
                if not corr_suggestion:
                    skipped.append({**info_base, 'reason': 'لا يوجد اقتراح'})
                    continue
                if corr_sample_size < min_sample:
                    skipped.append({**info_base, 'reason': f'عينة صغيرة ({corr_sample_size} أيام)'})
                    continue
                if has_chronological_conflict(d, punch_type, corr_suggestion):
                    skipped.append({**info_base, 'reason': '⛔ تعارض في الترتيب الزمني'})
                    continue

                # كل الشروط مرّت — نضيفه للمقترحات (لسه معلَّق، مش مطبَّق فعليًا)
                proposed_pending[pending_key] = {
                    'type':       'correction',
                    'key_base':   key_base,
                    'rev_key':    rev_key,
                    'value':      corr_suggestion,
                    'punch_role': punch_type,
                }
                applied.append(info_base)

    return {'applied': applied, 'skipped': skipped, 'pending_changes': proposed_pending}
