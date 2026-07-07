تمام، هنا نسخة مرتبة حسب ترتيب الـ Phases (0 → 1 → 2 → 3) بدون حذف أي معلومة، وكل حاجة داخل نفس الـ Phase مرتبة حسب الترتيب الزمني اللي حصلت بيه:

---

# progress.md

## Phase 0

- [Phase 0] بدأنا: هيكل المشروع + main.py + main_window.py + app_config.py + requirements.txt + packaging/build.spec.
- [Phase 0] ✅ نجح: العميل شغّل `python main.py` والنافذة فتحت فعليًا برسالة النجاح. لم يتم تجربة PyInstaller/exe بعد (اختياري، هيتأكد منه في Phase 9).

---

## Phase 1

- [Phase 1] بدأنا: db/models.py (كل الجداول من schema.md) + db/database.py (SQLite + init_db) + CompanyRepository + EmployeeRepository + AttendanceFileRepository + اختبارات tests/test_repositories.py (13 اختبار). main.py بيستدعي init_db() تلقائيًا الآن.
- [Phase 1] ✅ نجح: كل الـ 13 اختبار عدّت بنجاح (CRUD كامل: شركة/موظف/ملف شهر + Unique Constraints + شجرة الملفات + نقل الشهر). Phase 1 مكتملة.

---

## Phase 2

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

---

## Phase 3

- [Phase 3] الخطوة التالية (وقتها): حفظ نتائج التحليل في قاعدة البيانات (AttendanceDayRepository + PunchRepository + CorrectionRepository) بدل الذاكرة.

- [Phase 3] بدأنا: بناء واجهة شجرة الملفات والاستيراد.
  - ui/widgets/file_tree_sidebar.py: QTreeWidget لعرض (شركة → سنة → شهر)، قائمة سياقية (Right-click) لكل مستوى: فتح/حذف/إعادة تسمية، مع الحفاظ على حالة الطي/الفتح عند أي refresh.
  - ui/widgets/import_dialog.py: نافذة استيراد (اختيار ملف بزر أو Drag&Drop، اختيار شركة موجودة/جديدة + سنة + شهر، نوع الجهاز Hikvision/ZK Classic، وضع "فتح مؤقت Anonymous")، مع كتابة الملف فعليًا على القرص (data/<شركة>/<سنة>/<شهر>/) قبل استدعاء AttendanceFileRepository.create.
  - ui/main_window.py: تحديث كامل — ربط QDockWidget بالـ Sidebar، QStackedWidget بدل الشاشة الفارغة (placeholder + دور مكان Dashboard لـ Phase 4)، QStatusBar لعرض التعديلات المعلَّقة لاحقًا.

- [Phase 3] تم تعديل الكود عشان يطابق الـ Repositories الفعلية المرفوعة من العميل (CompanyRepository.list_all/create/rename/delete، AttendanceFileRepository.list_tree_by_company/get_by_company_year_month/create/delete) بدل الأسماء الافتراضية المفترضة أول مرة.

- [Phase 3] ⚠️ لم يتم اختبار التشغيل الفعلي بعد على جهاز العميل (وقتها) — بانتظار تجربة `python main.py` والتأكد من عدم وجود أخطاء (AttributeError/ImportError) خصوصًا في:
  - مسار `data/` الذي يُبنى نسبيًا من `import_dialog.py` (بافتراض أن `ui/widgets/` على بعد 3 مستويات من جذر المشروع — نفس منطق `database.py`).
  - التأكد من وجود `ui/widgets/__init__.py` فاضي.

- [Phase 3] الملفات تنتقل إلى data بشكل صحيح — التفرع الشجري الفعلي على جهاز العميل:

```
C:.
│   1_report-1.xls
│   app_config.py
│   claude.md
│   Guide.md
│   Instruction.md
│   main.py
│   oldapp.py
│   phases.md
│   progress.md
│   requirements.txt
│   schema.md
│   test.bat
│   test_fixture_file.py
│   ui.md
│
├───data
│   │   app.db
│   │
│   └───TALKHA
│       └───2026
│           ├───06
│           │       TALKHA_2026_06.xlsx
│           │       TALKHA_2026_06_original.bin
│           │
│           └───07
│                   TALKHA_2026_07.xlsx
│                   TALKHA_2026_07_original.bin
│
├───db
│   │   database.py
│   │   models.py
│   │   __init__.py
│   └───repositories
│           attendance_repository.py
│           company_repository.py
│           employee_repository.py
│           __init__.py
│
├───packaging
│       build.spec
│
├───services
│   │   __init__.py
│   └───parsers
│           common.py
│           hikvision_parser.py
│           zk_classic_parser.py
│           __init__.py
│
├───tests
│       test_parsers.py
│       test_repositories.py
│       __init__.py
│
└───ui
    │   main_window.py
    │   __init__.py
    └───widgets
            file_tree_sidebar.py
            import_dialog.py
```

- [Phase 3] الخطوة التالية (وقتها): بعد تأكيد نجاح فتح/استيراد/حذف/إعادة تسمية من الشجرة فعليًا، ننتقل لـ Phase 4 (Dashboard View + ربط services/parsers الموجودة من Phase 2 بعرض النتائج الفعلية بدل الـ placeholder الحالي).

- [Phase 3] 🐛 **مشكلة اكتُشفت:** لما يتم مسح ملف أو سنة من الواجهة، السجل يختفي من الشجرة لكنه يبقى موجودًا فعليًا في `data/` على القرص.

- [Phase 3] 🐛 **Bug تم اكتشافه وإصلاحه:** بعد فتح ملف من الشجرة كان البرنامج يطلع Traceback:
  `AttributeError: 'list' object has no attribute 'iterrows'` من داخل `ui/main_window.py` (السطر بتاع `for _, row in df.iterrows()`).

  **السبب الجذري:** `services/parsers/common.py` فيها دالة `build_summary_rows()` (البديلة لـ `_build_summary_df` الأصلية في `oldapp.py`) كانت بترجع `list[dict]` عادية بدل `pandas.DataFrame`. وبما إن `hikvision_parser.py` و`zk_classic_parser.py` بيرجعوا ناتج الدالة دي زي ما هو، فالـ `df` اللي بتوصل لـ `main_window.py` كانت فعليًا `list`، مش DataFrame — رغم إن كل الكود التاني (`dashboard_view.py`, `payroll_calculator.py`) مبني على افتراض إنها DataFrame زي `oldapp.py` الأصلي بالظبط.

  **الحل المُطبَّق:** تم تعديل آخر سطر في كل من:
  - `services/parsers/hikvision_parser.py`
  - `services/parsers/zk_classic_parser.py`

  بإضافة `import pandas as pd` وتغليف الناتج:
  ```python
  summary_rows = build_summary_rows(emp_days, log_names, log_depts)
  return pd.DataFrame(summary_rows), emp_days
  ```
  بدل `return build_summary_rows(...), emp_days` مباشرة. **لا يوجد أي تغيير في منطق الحساب نفسه** — فقط تصحيح نوع البيانات الراجعة ليطابق ما كانت عليه `_build_summary_df` في `oldapp.py`.

  ✅ تم تشغيل `pytest tests/test_parsers.py -v` بعد التعديل — كل الاختبارات (19) لسه عدّت بنجاح (لأن الاختبارات بتستهدف `common.py` مباشرة وليس الـ parsers نفسها). تم فتح نفس ملف الشهر اللي كان بيطلع فيه الخطأ والتأكد أن البرنامج يعمل بشكل سليم الآن ويعرض الـ Dashboard فعليًا.

  ⚠️ **درس مستفاد للمستقبل:** أي دالة جديدة تُنقل من `oldapp.py` ويتغيّر اسمها أثناء النقل (زي `_build_summary_df` → `build_summary_rows`) لازم يُتأكَّد من توافق **نوع الإرجاع (return type)** مع كل الأماكن المستهلكة له في باقي الطبقات (UI/Dashboard/Payroll)، مش بس التأكد من صحة القيم الرقمية داخل الاختبارات.

- [Phase 3] 🐛 **Bug تم اكتشافه (الحل مقترح، لم يُنفَّذ فعليًا بعد):** بخصوص مشكلة الحذف الجزئي المذكورة أعلاه — تم تشخيص السبب الجذري:

  في `services/paths.py`، الدالتان `delete_month_folder()` و`delete_company_folder()` كانتا تستخدمان:
  ```python
  shutil.rmtree(path, ignore_errors=True)
  ```
  فلو فشل الحذف الفعلي لأي سبب (ملف مفتوح في برنامج تاني وقت الحذف، صلاحيات Windows، الملف Read-only...)، كانت الدالة **تبلع الخطأ بصمت** بدون أي إشارة بالفشل. النتيجة: السجل يُحذف من قاعدة البيانات (SQLite) بنجاح، فيختفي من الشجرة بعد `refresh()`، لكن الملفات الفعلية على القرص تبقى كما هي لأن `rmtree` فشل داخليًا دون أن يُعلم أحدًا.

  **الحل المقترح (لم يُنفَّذ فعليًا بعد — بانتظار تأكيد التنفيذ):**
  - إضافة `onerror=_force_remove_readonly` بدل `ignore_errors=True` في `shutil.rmtree` — بحيث لو الملف Read-only، يشيل الصفة دي ويحاول الحذف تاني (بيحل أغلب مشاكل rmtree الشائعة على Windows).
  - تعديل الدالتين ليرجّعوا `bool` (نجح الحذف بالكامل أم لا) بدل الافتراض الحالي إن كل حاجة نجحت دائمًا.
  - تعديل `AttendanceFileRepository.delete()` و`CompanyRepository.delete()` ليستقبلوا الـ `bool` الراجع، ولو `False`، يُبلَّغ المستخدم عبر `QMessageBox.warning` في `file_tree_sidebar.py` أن السجل اتمسح من البرنامج لكن فيه ملفات فعلية فضلت على القرص (مثلاً بسبب ملف مفتوح وقت الحذف في Excel).

  ⏳ **ملاحظة:** هذا الحل لم يُطبَّق كملفات فعلية بعد في هذه الجلسة — فقط تم تشخيصه واقتراح الحل. يجب تنفيذه فعليًا وتجربته (خصوصًا سيناريو: فتح ملف الإكسل يدويًا في برنامج خارجي ثم محاولة حذفه من داخل البرنامج) قبل اعتبار المشكلة مُغلَقة.

- [Phase 3] ⚠️ **ملاحظة توثيقية:** تم التأكد أن `ui/widgets/__init__.py` غير موجود فعليًا على القرص (بينما كل المجلدات التانية في المشروع عندها `__init__.py` فاضي). Python كان يعمل رغم غيابه بسبب دعم Implicit Namespace Packages، لكن هذا خطر كامن في Phase 9 (PyInstaller) لأن التغليف أحيانًا بيفشل في اكتشاف/تضمين namespace packages بشكل صحيح داخل الـ exe. **يجب إنشاء ملف `ui/widgets/__init__.py` فاضٍ قبل الوصول لمرحلة التغليف.**

- [Phase 3] ✅ **تحديث:** بعد إصلاح مشكلة `iterrows()` أعلاه، أكّد العميل أن البرنامج أصبح يعمل بشكل جيد — فتح الملفات من الشجرة، والاستيراد، وعرض الـ Dashboard كلها شغّالة حاليًا بدون أخطاء ظاهرة.

- [Phase 3] الخطوة التالية (الحالية):
  1. تنفيذ فعلي لحل مشكلة الحذف الجزئي (rmtree + ignore_errors) الموضحة أعلاه، وتجربته على سيناريو ملف مقفول فعليًا.
  2. إنشاء `ui/widgets/__init__.py` فاضي.
  3. بعد تأكيد الاثنين أعلاه، ننتقل رسميًا لـ Phase 4 (Dashboard View + ربط services/parsers بعرض النتائج الفعلية) — علمًا بأن أجزاء كبيرة من Phase 4 (dashboard_view.py, payroll_table_model.py) موجودة بالفعل ومربوطة في main_window.py وتعمل حاليًا.


  

  شكرًا على الصورة — تمام، واضح إن الكارت (`cell`) في `_refresh_rate_grid` ضيق جدًا لأنه معتمد على حجم المحتوى الطبيعي بدون أي حد أدنى أو تباعد داخلي. هصلح الاتنين مع بعض: إضافة تبويب "📅 أيام الحضور" + تكبير ارتفاع كارت الموظف وتحسين التباعد.

  

إليك ملف `dashboard_view.py` كامل بعد التعديلين:## ملخص التعديلات

  

**1) مشكلة الـ Height الضيق (من الصورة):**

- `cell.setMinimumHeight(96)` بدل ما كان بدون أي حد أدنى.

- زودت `setContentsMargins(12, 10, 12, 10)` و`setSpacing(6)` جوه الكارت.

- `rate_spin` و`view_btn` بقى ليهم `setMinimumHeight(30)`.

- `rates_scroll.setMaximumHeight` زودتها من 260 لـ 320 عشان تبان الكروت الأكبر بشكل أوضح.

  

**2) تبويب "📅 أيام الحضور" الناقص:**

- أضفت `chart_attendance_view` كتبويب ثالث.

- أضفت دالة `_make_attendance_chart()` بتعمل عمودين (حضور + غياب) لكل موظف، مطابقة لسطر `oldapp.py`:

  ```python

  filtered[['الاسم', 'أيام الحضور', 'أيام الغياب']].set_index('الاسم')

  ```

  

**+ ملاحظة إضافية اتصلحت مجانًا:** بما إننا لمسنا `_update_charts` أصلاً، صلّحتها كمان تاخد البيانات من `_current_filtered_df()` (المفلترة فعليًا) بدل الجدول الكامل — لأن كنا هنؤجلها لكن التعديل كان في نفس الدالة أصلاً فمفيش تكلفة إضافية، وده بيقفل نقطة كانت متسجّلة في الملاحظات المؤجَّلة.

  
  Phase 04 انتهى تقريبا باقي شيء بسيط