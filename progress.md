# progress.md

- [Phase 0] بدأنا: هيكل المشروع + main.py + main_window.py + app_config.py + requirements.txt + packaging/build.spec.
- [Phase 0] ✅ نجح: العميل شغّل `python main.py` والنافذة فتحت فعليًا برسالة النجاح. لم يتم تجربة PyInstaller/exe بعد (اختياري، هيتأكد منه في Phase 9).
- [Phase 1] بدأنا: db/models.py (كل الجداول من schema.md) + db/database.py (SQLite + init_db) + CompanyRepository + EmployeeRepository + AttendanceFileRepository + اختبارات tests/test_repositories.py (13 اختبار). main.py بيستدعي init_db() تلقائيًا الآن.
- [Phase 1] ✅ نجح: كل الـ 13 اختبار عدّت بنجاح (CRUD كامل: شركة/موظف/ملف شهر + Unique Constraints + شجرة الملفات + نقل الشهر). Phase 1 مكتملة.
- [Phase 2] بدأنا: نقل الدوال حرفيًا من oldapp.py (بدون أي تغيير منطقي) إلى:
  - services/parsers/common.py: كل الدوال المساعدة المشتركة.
  - services/parsers/hikvision_parser.py: parse_file_hikvision.
  - services/parsers/zk_classic_parser.py: parse_file (الصيغة القديمة Att.log report).
  - tests/test_parsers.py: 19 اختبار وحدة — كلها ✅ عدّت بنجاح.
- [Phase 2] ⚠️ ملاحظة: سلوك موروث من oldapp.py — لو أول يوم في الشهر فيه بصمة قبل cutoff ومفيش يوم سابق، البصمة تُفقد (شرط `if i > 0`). تم توثيق وقبول هذا السلوك كما هو (التزام بـ "لا تغيير منطقي").
- [Phase 2] ✅ **اختبار ملف فعلي من العميل (Golden Output):**
  - ملف: 1_report-1.xls (925,696 بايت) — ZK Classic
  - النتائج:
    * عدد الموظفين: 93
    * إجمالي الساعات: 1,821.41
    * إجمالي أيام الحضور: 297
    * إجمالي أيام الغياب: 2432
    * إجمالي أيام ببصمة ناقصة: 50
  - ✅ الأرقام منطقية وصحيحة ومتطابقة تمامًا مع oldapp.py (Streamlit).
  - ✅ تم الاختبار على Windows 10 Python 3.10 — كل الدوال تعمل بدون أخطاء.
- [Phase 2] ✅ **مكتملة 100%** — النقل الحرفي نجح، الاختبارات تعدّ، الملفات الحقيقية تعطي نتائج صحيحة ومتطابقة.

- [Phase 3] الخطوة التالية: حفظ نتائج التحليل في قاعدة البيانات (AttendanceDayRepository + PunchRepository + CorrectionRepository) بدل الذاكرة.