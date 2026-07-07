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
تحديث انتهى Phase 04

- [Phase 5] ✅ البرنامج يعمل بكفاءة بعد إضافة الملفات الناقصة (corrections_engine.py، pending_changes.py، review_panel.py، day_editor_dialog.py، correction_state_repository.py). لم تُلاحَظ أي مشاكل عند الاختبار اليدوي.
- [Phase 5] 🐛 Bug تم حله: AppSettings → AppSetting (الاسم الصحيح في db/models.py). السبب: خطأ في اسم الكلاس عند كتابة correction_state_repository.py لأول مرة.

انتهى Phase 05
تم ملاحظة مشكلة وهي التالي: 
عند تعديل اسعار الموظفين ثم اغلاق البرنامج وفتحه يعود مرتبات لبعض الموظفين 
حل هذه المشكلة قبل الانتقال لـ Phase 06

- [Phase 5] 🐛 **تشخيص كامل لمشكلة رجوع أسعار الموظفين (تم التنفيذ):**

  **تأكيد أولي من قاعدة البيانات:** السعر بيتحفظ صح في `employee_rate_defaults`
  (مثال: `employee_id=73` لموظفة اسمها Salwa، `hourly_rate=2.0` محفوظ فعليًا).
  المشكلة إذًا مش في الحفظ (`set_rate`) ولا في القراءة بالـ JOIN
  (`get_rates_map_by_employee_id` بتعمل فلترة صح بـ `company_id`) — المشكلة في
  الحلقة اللي بتربط `external_code` (اللي جاي من ملف البصمة) بـ `employee.id`
  (اللي جاي من القاعدة) في `main_window.py`.

  **1) 🔴 خطأ حرج مكتشف: `main_window.py` فيه `IndentationError` فعلي.**
  داخل `_run_analysis`، السطر:
  ```python
  if company_id is not None:
  for _, row in df.iterrows():   # ← نفس مستوى إزاحة الـ if، مش جواه!
  ```
  ده كود مش هيشتغل من الأساس (الملف مش هيتفتح/يتستورد). تم تأكيد الخطأ فعليًا
  بتشغيل `ast.parse()` على الملف. **تم إصلاحه:** رجّعت الـ `for` جوه الـ `if`
  بإزاحة صحيحة، وشلت لفة `df.iterrows()` المكررة اللي كانت متعشّشة جوه بعض
  بلا داعي، ونقلت تحميل `rates_by_employee_id` (والحلقة اللي بتبني
  `hourly_rates`) بره اللفة الخارجية بالكامل — يعني تتنفذ **مرة واحدة** بعد
  ما يخلص بناء `_eid_to_employee_id` لكل الموظفين، مش مرة لكل صف.

  **2) 🔴 السبب الجذري الأرجح لرجوع السعر القديم:**
  `EmployeeRepository.get_or_create` كانت بتستخدم:
  ```python
  self.session.query(Employee).filter_by(company_id=..., external_code=...).first()
  ```
  بدون `order_by`. لو فيه أكتر من صف `Employee` بنفس
  `(company_id, external_code)` في القاعدة فعليًا (ممكن يكون حصل قبل ما يتفعّل
  قيد `UNIQUE(company_id, external_code)` في `models.py`، أو من استيراد متكرر
  قبل ما يتظبط `get_or_create`) — SQLite/`.first()` من غير `order_by` **مش
  بيضمن نفس الترتيب كل مرة**. يعني كل ما تفتح نفس الشهر تاني، ممكن يرجعلك
  `employee.id` مختلف عن اللي معاه السعر المحفوظ فعليًا (`id=73`)، فيظهر السعر
  0 أو قديم رغم إن القاعدة سليمة 100%.

  **الحل المُطبَّق:** أضفت `.order_by(Employee.id.asc())` في `get_or_create`
  عشان الاختيار يبقى حتمي (دايمًا نفس الموظف الأقدم) حتى لو فيه صفوف مكررة.

  **⚠️ خطوة تحقق مطلوبة من العميل قبل إغلاق المشكلة نهائيًا:**
  شغّل الاستعلام ده على `data/app.db` (عبر أي أداة SQLite، أو سكريبت بسيط) للتأكد
  ما إذا كان فيه صفوف مكررة فعليًا في القاعدة الحالية:
  ```sql
  SELECT company_id, external_code, COUNT(*) c
  FROM employees
  GROUP BY company_id, external_code
  HAVING c > 1;
  ```
  لو النتيجة فاضية → يبقى `order_by` كانت إجراء وقائي فقط والمشكلة كانت بالكامل
  من الـ `IndentationError` (يعني الكود القديم كان أصلًا بيطلع Exception ويمنع
  تحديث `hourly_rates` بالكامل في بعض الحالات، أو نسخة قديمة مختلفة شوية كانت
  شغالة فعليًا على جهاز العميل غير المرفوعة هنا).
  لو النتيجة فيها صفوف → يبقى فيه تنضيف مطلوب (Migration بسيط لدمج الصفوف
  المكررة) قبل الانتقال لـ Phase 06، ولازم يُضاف قيد `UNIQUE(company_id,
  external_code)` فعليًا في `models.py` لو مش موجود، لمنع تكرار الظاهرة مستقبلًا.

  ✅ الملفات المُصلَحة: `main_window.py`, `employee_repository.py`.
  لا تغيير في `employee_rate_repository.py` — منطق الحفظ والقراءة فيها كان
  سليمًا من البداية.

- [Phase 5] 🐛 **مشكلة تانية مختلفة (بعد تجربة العميل فعليًا):** لسه المرتبات
  بترجع للقيمة القديمة بعد إعادة الفتح، لكن هنا تحديدًا لما السعر الجديد
  المُدخَل = **صفر** (جرّب المستخدم يغيّر سعر Menna وHossam لـ 0.00).

  **السبب الجذري (مؤكَّد من الكود مباشرة):** أول سطر في
  `EmployeeRateRepository.set_rate`:
  ```python
  if hourly_rate is None or hourly_rate <= 0:
      return
  ```
  كان بيتجاهل بصمت أي محاولة حفظ لسعر = 0 أو أقل — يعني الصف القديم في
  `employee_rate_defaults` (بالسعر القديم 1.00 / 2.00) مكانش بيتحدّث أصلًا في
  القاعدة. الواجهة كانت بتوريك 0.00 مؤقتًا في الـ Spinbox بس ده شكل بصري فقط،
  الحفظ الفعلي في القاعدة ما كانش بيحصل خالص. فلما تقفل وتفتح، بترجع القيمة
  القديمة لأنها فعليًا ما كانت اتغيّرتش من الأساس.

  **الحل المُطبَّق:** غيّرت الشرط ليفرّق بين `None` (لا قيمة أصلًا — تجاهل)
  وبين قيمة سالبة فقط (تجاهل)، وسمحت بحفظ **0 كقيمة حقيقية مقصودة**:
  ```python
  if hourly_rate is None or hourly_rate < 0:
      return
  ```

  ✅ الملف المُصلَح: `employee_rate_repository.py`.

  ⏳ **بانتظار تأكيد العميل بعد التجربة الفعلية:** غيّر سعر موظف لـ 0.00، اقفل
  البرنامج وافتحه تاني، وتأكد إن السعر فضل 0.00 (مش رجع للقيمة القديمة).

  ⚠️ **ملاحظة جانبية لوحظت في لقطات الشاشة (لم تُحسم بعد):** عدد الموظفين
  وعدد "بصمات ناقصة" وإجمالي الساعات اختلفوا بين لقطتين لنفس الملف (14 موظف
  مقابل 12، 10 بصمات ناقصة مقابل 9). يحتاج توضيح من العميل: هل اللقطتين
  لفتحتين مختلفتين فعليًا للملف في وقتين مختلفين (فيكون طبيعي)، أم لنفس الفتحة
  بالظبط (فيبقى Bug منفصل يحتاج تتبّع في `dashboard_view.py` غير المرفوع حاليًا)؟

  ✅ **تحديث من العميل:** الفرق طبيعي ومقصود — الموظف اللي سعر ساعته = 0 مش
  بيتحسب كموظف "له مرتب" في عداد الداشبورد، فطبيعي إن العدد يقل/يزيد حسب
  الأسعار المُدخَلة. **المشكلة اتقفلت نهائيًا.**

---

## Phase 6 — Bulk Smart Apply وأنماط الشيفتات

- [Phase 6] بدأنا: نقل `has_chronological_conflict` و`bulk_smart_apply_all` من
  `oldapp.py` (سطر 3673 و3729 بالترتيب) إلى `services/corrections_engine.py`
  (جنب `apply_overrides` الموجودة من Phase 5، مطابقًا لهيكل المجلدات في
  `claude.md`). `assign_shift_patterns` و`classify_lone_punch` كانا اتنقلوا
  بالفعل ضمن `services/parsers/common.py` من Phase 2 (مُستخدَمين فعليًا من
  الـ parsers) — لا حاجة لنقلهم تاني، فقط استوردت `classify_lone_punch` من
  هناك داخل `corrections_engine.py`.

  **التغيير الوحيد غير المنطقي (مطلوب لأن الأصل Streamlit-specific):**
  - الأصل كان بيقرأ `corrections`/`pending`/`day_overrides` من
    `st.session_state` مباشرة، وبيستدعي `add_pending_change()` (دالة Streamlit
    غير موجودة في هذا المشروع) عشان يضيف الاقتراح مباشرة لحالة التطبيق.
  - النسخة الجديدة: `bulk_smart_apply_all(emp_days, corrections, pending,
    day_overrides, min_sample=3)` بتاخد الثلاثة كمعاملات صريحة، وبترجع
    `pending_changes` كـ dict (`{pending_key: correction_payload}`) بدل ما
    تعدّل حاجة مباشرة — **دالة معاينة فقط (Preview)، زي ما كانت بالظبط في
    الواجهة الأصلية (زرار "معاينة" ثم "تأكيد وتطبيق" منفصلين)**.
  - منطق القرار نفسه (confidence == 'high'، corr_sample_size >= min_sample،
    `has_chronological_conflict`) **لم يتغيّر حرفًا واحدًا** عن الأصل.

  ⏳ **الخطوة التالية:** بناء `QDialog` معاينة (Preview Table) في الواجهة يعرض
  `applied`/`skipped` من `bulk_smart_apply_all`، وزرّي "✅ تأكيد وتطبيق" (يدمج
  `pending_changes` الراجعة في نظام Pending Changes الحالي لـ
  `EmployeeDetailView` ثم يستدعي `apply_overrides`) و"❌ إلغاء" — بنفس تصميم
  `phases.md` (Phase 6: "معاينة قبل التطبيق تعمل، والإلغاء يترك البيانات دون
  تغيير"). محتاجين نشوف `employee_detail_view.py` و`pending_changes.py`
  الحاليين (غير مرفوعين بعد) عشان ندمج الزرار في المكان الصح.

  ✅ الملف المُعدَّل: `corrections_engine.py` (تمت إضافة الدالتين في نهايته،
  بدون أي تغيير على `apply_overrides` أو الدوال المساعدة الموجودة).

- [Phase 6] ✅ **تم ربط الزر فعليًا في الواجهة:**
  - ملف جديد `ui/widgets/bulk_smart_apply_dialog.py`: `BulkSmartApplyDialog`
    (QDialog معاينة فقط) — جدول "applied" (اليوم/البصمة/النوع/الثقة/حجم
    العينة/المقترح) + جدول "skipped" (اليوم/البصمة/السبب) لو موجودين، وزرّي
    "✅ تأكيد وتطبيق N تصحيح" / "❌ إلغاء". لو مفيش أي applied، بيعرض رسالة
    "لا توجد بصمات تستوفي شروط التطبيق الآمن" + زر إغلاق فقط — مطابق تمامًا
    لسلوك oldapp.py الأصلي.
  - `employee_detail_view.py`: زر جديد "🤖 Bulk Smart Apply" جنب "🔄 استعادة
    الافتراضي" في الصف العلوي. عند الضغط: يستدعي `bulk_smart_apply_all` على
    `{self.eid: self.days}` فقط (نطاق الموظف الحالي المفتوح، مش كل الموظفين
    زي oldapp.py الأصلي — لأن الزر موجود داخل شاشة تفاصيل موظف واحد حسب
    `ui.md` §3.4)، مع تمرير `self.corrections`/`self.pending.get_all()`/
    `self.day_overrides` الحاليين. لو المستخدم ضغط "✅ تأكيد وتطبيق" جوه الـ
    Dialog، بيتم دمج `pending_changes` الراجعة في `PendingChangesStore`
    الحالي (`self.pending.add(...)` لكل عنصر) ثم `_refresh_all()` — يعني
    التصحيحات المقترحة بتتحط في حالة "معلَّق" زي أي تصحيح يدوي بالظبط، ولسه
    محتاجة ضغطة "✅ Apply" الرئيسية عشان تتثبّت فعليًا في corrections
    وتتحفظ في القاعدة (نفس فلسفة الشاشة الحالية من Phase 5 — Preview ثم
    Apply منفصلين، تمامًا زي طلب `phases.md`: "الإلغاء يترك البيانات دون
    تغيير").

  ⚠️ **قرار مؤقت يحتاج مراجعة:** `min_sample=3` مثبَّت (Hardcoded) حاليًا في
  `_on_bulk_smart_apply_clicked` — الأصل في `oldapp.py` كان فيه Slider
  (`min_sample_bulk`) يتحكم فيه المستخدم. لسه معملناش شاشة/عنصر تحكم لده في
  PySide6. **لازم نضيفه لاحقًا** (يُقترح: SpinBox بجانب الزر أو في شاشة
  الإعدادات العامة Phase 8) قبل اعتبار Phase 6 مكتملة 100%.

  ✅ الملفات: `bulk_smart_apply_dialog.py` (جديد)، `employee_detail_view.py`
  (معدَّل).

سيتم عمل Skip لـ Phase الـ Export ونقله الى اخر البرنامج بعد ان ننهي كل شيء
ننتقل الى Phase


Phase 08 — الإعدادات (Settings: Cutoff / Saturate / Tolerance)، حسب phases.md.
الهدف: نقل الـ Sliders الخاصة بإعدادات الشيفت مع الحفظ التلقائي لكل ملف شهر.

Slider لحد Redistribute (cutoff_hour).
Slider لحد Saturate (saturate_min).
Checkbox + Slider لنظام التسامح مع المغادرة المبكرة (tolerance_enabled / tolerance_minutes).
تُحفظ تلقائيًا في file_settings لكل ملف شهر (Auto-save عند التغيير، بدون زر حفظ منفصل).

اختبار القبول:

تغيير أي إعداد → يُحفظ فورًا.
إغلاق الملف وإعادة فتحه → الإعدادات المحفوظة تُسترجع بنفس القيم.
تغيير الإعدادات يعيد حساب الساعات فورًا بشكل صحيح.

بما إن FileSettingsRepository و_DefaultFileSettings وget_or_create للإعدادات موجودين بالفعل في main_window.py (شفتهم يُستخدَموا في _run_analysis)، غالبًا الجزء الأكبر من الـ Backend جاهز، والمطلوب أساسًا شاشة/Widget للإعدادات في الواجهة.
عشان أبدأ، ابعتلي:

file_settings_repository.py
