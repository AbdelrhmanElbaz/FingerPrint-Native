# test_fixture_detailed.py
# سكريبت اختبار مفصّل — عرض كل الموظفين وليس أول 5 فقط
# التشغيل: python test_fixture_detailed.py
#
# الهدف: عرض البيانات الكاملة لكل موظف لمقارنتها بـ oldapp.py (Streamlit)

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from services.parsers.zk_classic_parser import parse_file as parse_file_zk

file_path = Path("1_report-1.xls")

if not file_path.exists():
    print(f"❌ الملف {file_path} غير موجود في المجلد الحالي")
    sys.exit(1)

file_bytes = file_path.read_bytes()
print(f"✅ تم قراءة الملف: {file_path.name} ({len(file_bytes):,} بايت)\n")

print("=" * 100)
print("قراءة كـ ZK Classic (Att.log report)")
print("=" * 100)

try:
    summary_rows, emp_days = parse_file_zk(file_bytes, cutoff_hour=3.0)
    
    print(f"\n📊 ملخص عام:")
    print(f"  - عدد الموظفين: {len(summary_rows)}")
    print(f"  - عدد الأيام المعالجة (من أول موظف): {len(emp_days.get(list(emp_days.keys())[0], []))}")
    
    # إجمالي الساعات والأيام
    total_hours = sum(r['work_hours'] for r in summary_rows)
    total_att_days = sum(r['attendance_days'] for r in summary_rows)
    total_absent_days = sum(r['absent_days'] for r in summary_rows)
    total_incomplete = sum(r['incomplete_days'] for r in summary_rows)
    
    print(f"\n📈 إجمالي:")
    print(f"  - إجمالي الساعات: {total_hours:,.2f}")
    print(f"  - إجمالي أيام الحضور: {int(total_att_days)}")
    print(f"  - إجمالي أيام الغياب: {int(total_absent_days)}")
    print(f"  - إجمالي أيام ببصمة ناقصة: {int(total_incomplete)}")
    
    # عرض كل الموظفين
    print(f"\n" + "=" * 100)
    print("🧑‍💼 قائمة كل الموظفين:")
    print("=" * 100)
    
    # ترتيب حسب ID
    sorted_rows = sorted(summary_rows, key=lambda r: int(r['id']))
    
    for i, row in enumerate(sorted_rows, 1):
        incomplete_mark = f"  | ⚠️ {int(row['incomplete_days'])} ناقصة" if row['incomplete_days'] > 0 else ""
        print(f"{i:>3}. ID: {row['id']:>4} | {row['name']:<25} | ساعات: {row['work_hours']:>7.2f} | حضور: {int(row['attendance_days']):>2} يوم | غياب: {int(row['absent_days']):>2}{incomplete_mark}")
    
    print("\n" + "=" * 100)
    print("📝 ملخص نهائي للمقارنة بـ oldapp.py (Streamlit):")
    print("=" * 100)
    print(f"""
✅ Phase 2 (Native) - ZK Classic Parser:
   - عدد الموظفين: {len(summary_rows)}
   - إجمالي الساعات: {total_hours:,.2f}
   - إجمالي أيام الحضور: {int(total_att_days)}
   - إجمالي أيام الغياب: {int(total_absent_days)}
   - إجمالي أيام ببصمة ناقصة: {int(total_incomplete)}

📋 يجب مقارنة الأرقام أعلاه بـ oldapp.py (Streamlit) بنفس الملف (1_report-1.xls)

إذا تطابقت الأرقام تمامًا = ✅ Phase 2 مكتملة بنجاح 100%
إذا اختلفت = ❌ نحتاج نحقق في الفرق وتصحيحه
""")
    
except Exception as e:
    print(f"❌ فشل: {type(e).__name__}: {e}\n")
    import traceback
    traceback.print_exc()