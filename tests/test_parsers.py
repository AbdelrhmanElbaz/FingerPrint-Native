# tests/test_parsers.py
# اختبارات Phase 2 — الدوال الأساسية في services/parsers/common.py
# التشغيل: pytest tests/test_parsers.py -v
#
# ⚠️ ملاحظة مهمة (راجع phases.md):
# هذه اختبارات وحدة (Unit Tests) على الخوارزميات الأساسية فقط.
# اختبار الـ Regression الحقيقي (مقارنة نتائج ملفات إكسل فعلية من العميل
# مع "Golden Output" من نسخة Streamlit القديمة) يحتاج ملفات fixtures حقيقية
# غير متوفرة حاليًا — يجب إضافتها في tests/fixtures/ قبل اعتماد Phase 2 كمكتملة.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from services.parsers.common import (
    remove_close_punches,
    to_minutes,
    minutes_diff,
    fmt_hm,
    circular_mean,
    circular_dist,
    redistribute_overnight_punches,
    saturate_punches,
    assign_shift_patterns,
    classify_lone_punch,
    cluster_times_circular,
)


# ─── remove_close_punches ──────────────────────────────────────────────────

def test_remove_close_punches_removes_near_duplicate():
    times = ["8:00", "8:05", "8:20"]
    result = remove_close_punches(times, tolerance_minutes=10)
    assert result == ["8:00", "8:20"]


def test_remove_close_punches_keeps_all_if_far_apart():
    times = ["8:00", "12:00", "17:00"]
    result = remove_close_punches(times, tolerance_minutes=10)
    assert result == times


def test_remove_close_punches_single_or_empty():
    assert remove_close_punches([], tolerance_minutes=10) == []
    assert remove_close_punches(["8:00"], tolerance_minutes=10) == ["8:00"]


# ─── to_minutes / minutes_diff / fmt_hm ────────────────────────────────────

def test_to_minutes_basic():
    assert to_minutes("08:30") == 510
    assert to_minutes("") is None
    assert to_minutes("--:--") is None


def test_minutes_diff_normal():
    assert minutes_diff("08:00", "16:00") == 480


def test_minutes_diff_crossing_midnight():
    # شيفت يمتد بعد منتصف الليل: حضور 22:00، انصراف 02:00 (اليوم التالي)
    assert minutes_diff("22:00", "02:00") == 240  # 4 ساعات


def test_fmt_hm():
    assert fmt_hm(0) == "0:00"
    assert fmt_hm(90) == "1:30"
    assert fmt_hm(None) == "0:00"


# ─── circular_mean / circular_dist (حالة منتصف الليل الحرجة) ──────────────

def test_circular_mean_overnight_case():
    # 23:00 (1380 دقيقة) و 01:00 (60 دقيقة) → المتوسط الصحيح يجب أن يكون قرب 00:00
    result = circular_mean([1380, 60])
    # نتوقع قيمة قريبة من منتصف الليل (0) وليس 12 ظهرًا (720)
    assert circular_dist(result, 0) < 5


def test_circular_dist_wraparound():
    # المسافة بين 23:50 و 00:10 يجب أن تكون 20 دقيقة (مش 1400+)
    assert circular_dist(1430, 10) == 20


# ─── redistribute_overnight_punches (حالة الشيفت الليلي) ──────────────────

def test_redistribute_moves_early_morning_punch_to_previous_day():
    raw_punches = {
        "emp1": {
            1: ["22:00"],       # حضور يوم 1 مساءً
            2: ["02:00", "06:00"],  # بصمة بعد منتصف الليل (تخص يوم 1) + انصراف طبيعي
        }
    }
    result = redistribute_overnight_punches(raw_punches, cutoff_hour=3.0)
    # بصمة 02:00 لازم تترحّل ليوم 1 لأنها قبل الـ cutoff (3:00 ص)
    assert result["emp1"][1] == ["22:00", "02:00"]
    assert result["emp1"][2] == ["06:00"]


def test_redistribute_does_not_move_punch_after_cutoff():
    raw_punches = {
        "emp1": {
            1: ["22:00"],
            2: ["05:00", "14:00"],  # 05:00 بعد الـ cutoff (3:00) → لا تترحّل
        }
    }
    result = redistribute_overnight_punches(raw_punches, cutoff_hour=3.0)
    assert result["emp1"][1] == ["22:00"]
    assert result["emp1"][2] == ["05:00", "14:00"]


def test_redistribute_no_previous_day_drops_punch():
    """
    ⚠️ سلوك موروث من النسخة الأصلية (oldapp.py) — موثّق هنا عن قصد، وليس تغييرًا:
    لو اليوم الأول في الشهر فيه بصمة قبل الـ cutoff، ومفيش يوم سابق له في نفس
    الملف نرحّل له البصمة، فإن الكود الأصلي (شرط `if i > 0`) يتجاهل هذه البصمة
    نهائيًا (فقدان بيانات طفيف لأول يوم فقط). ننقل هذا السلوك كما هو تمامًا
    التزامًا بمبدأ "لا تغيير في منطق العمل إلا لو طُلب صراحة" (claude.md §5).
    لو العميل يعتبر هذا خطأ يجب إصلاحه، يجب أن يكون قرارًا واعيًا منفصلاً
    وليس ضمن Phase 2 (نقل حرفي).
    """
    raw_punches = {"emp1": {1: ["01:00", "09:00"]}}
    result = redistribute_overnight_punches(raw_punches, cutoff_hour=3.0)
    assert result["emp1"][1] == ["09:00"]  # بصمة 01:00 فُقدت — سلوك أصلي موروث


# ─── saturate_punches (يؤثر فقط على آخر بصمة، ولا يلمس غيرها) ─────────────

def test_saturate_clamps_only_last_punch_within_window():
    raw_punches = {
        "emp1": {
            1: ["05:55", "14:25"],   # آخر بصمة (14:25) خارج نافذة منتصف الليل → لا تتأثر
            2: ["14:00", "00:52"],   # آخر بصمة (00:52) داخل النافذة وتتجاوز 50 → تصبح 00:50
        }
    }
    result = saturate_punches(raw_punches, saturate_min=50)
    assert result["emp1"][1] == ["05:55", "14:25"]  # بدون تغيير
    assert result["emp1"][2] == ["14:00", "00:50"]  # تم الـ Clamp


def test_saturate_does_not_touch_first_punch_even_if_in_window():
    # بصمة الحضور (الأولى) تقع في نافذة منتصف الليل لكن يجب ألا تُلمس أبدًا
    raw_punches = {"emp1": {1: ["00:10", "16:00"]}}
    result = saturate_punches(raw_punches, saturate_min=5)
    assert result["emp1"][1][0] == "00:10"  # لم تتغيّر رغم أنها > saturate_min


def test_saturate_empty_day_unaffected():
    raw_punches = {"emp1": {1: []}}
    result = saturate_punches(raw_punches, saturate_min=30)
    assert result["emp1"][1] == []


# ─── حالات حرجة إضافية (مطلوبة صراحة في phases.md) ─────────────────────────

def make_day(day_num, raw_times, status="حضور"):
    """مساعد لبناء يوم بصيغة emp_days المتوقعة."""
    return {
        "day": f"{day_num:02d}",
        "status": status,
        "total_min": 0,
        "incomplete": len(raw_times) % 2 == 1,
        "punch_pairs": [],
        "needs_review": [],
        "raw_times": raw_times,
        "tolerance_added": 0,
    }


def test_single_punch_day_classified_correctly():
    """يوم ببصمة واحدة فقط — يجب تصنيفها بناءً على الأيام الأخرى المكتملة."""
    days = [
        make_day(1, ["08:00", "16:00"]),
        make_day(2, ["08:05", "16:10"]),
        make_day(3, ["08:10"]),  # بصمة وحيدة قريبة من نمط الحضور المعتاد
    ]
    result = classify_lone_punch("08:10", days, shift_pattern=None)
    assert result["type"] == "check_in"
    assert result["confidence"] in ("high", "low")


def test_day_without_any_punches():
    """يوم بدون أي بصمات — يجب ألا يسبب أي استثناء عند تعيين shift_pattern."""
    emp_days = {
        "emp1": [
            make_day(1, ["08:00", "16:00"]),
            make_day(2, [], status="غياب"),
        ]
    }
    # لا يجب أن يرمي استثناء
    assign_shift_patterns(emp_days)
    assert emp_days["emp1"][1]["shift_pattern"] is None


def test_month_with_variable_day_counts():
    """يجب أن تعمل الدوال بغض النظر عن عدد أيام الشهر (28/29/30/31)."""
    for days_in_month in (28, 29, 30, 31):
        raw_punches = {
            "emp1": {d: ["08:00", "16:00"] for d in range(1, days_in_month + 1)}
        }
        result = redistribute_overnight_punches(raw_punches, cutoff_hour=3.0)
        assert len(result["emp1"]) == days_in_month


def test_overnight_shift_spanning_midnight_full_scenario():
    """
    سيناريو كامل: شيفت يبدأ الساعة 22:00 وينتهي 06:00 اليوم التالي.
    بعد Redistribute، يجب أن يُحسب اليوم بالكامل كفترة عمل واحدة متصلة.
    """
    raw_punches = {
        "emp1": {
            10: ["22:00"],
            11: ["02:00", "16:00"],  # 02:00 بعد منتصف الليل تخص يوم 10
        }
    }
    result = redistribute_overnight_punches(raw_punches, cutoff_hour=3.0)
    assert result["emp1"][10] == ["22:00", "02:00"]
    diff = minutes_diff(result["emp1"][10][0], result["emp1"][10][1])
    assert diff == 240  # 4 ساعات من 22:00 إلى 02:00
