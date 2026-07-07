# CLAUDE.md — نظام الحضور والرواتب (Native Rebuild)

> هذا الملف هو المرجع الأساسي لأي عمل على المشروع. أي كود يُكتب لازم يلتزم بالمبادئ هنا.

---

## 1. نظرة عامة على المشروع

برنامج مكتبي (Desktop) **أوفلاين بالكامل** لإدارة حضور وانصراف الموظفين وحساب الرواتب، بناءً على ملفات تصدير من أجهزة البصمة (Fingerprint Machines). يُستخدم من عميل واحد (أو أكثر) بشكل محلي على جهاز Windows، بدون إنترنت، بدون تسجيل دخول أو ترخيص.

### المشكلة اللي بنحلها
النسخة الحالية مبنية بـ **Streamlit**، وده بيسبب:
- كل تفاعل (زرار، إدخال رقم) بيعمل **rerun لكامل الصفحة** → بطء ملحوظ مع الملفات الكبيرة.
- الواجهة أساسًا **صفحة ويب جوه متصفح مضمّن** — مش تطبيق Native حقيقي، وده ظاهر من الحاجة لحقن JS يدوي في iframe الأب عشان مجرد نعمل زرار Sidebar شكله طبيعي (انظر الكود الأصلي — hack كامل بـ MutationObserver ومحاولات fallback).
- `st.session_state` مش موديل بيانات حقيقي — بيتحول بسهولة لباجات صعبة التتبع (نسيان مفتاح، تعارض بين pending changes والقيم الفعلية... إلخ).
- الحجم والاستهلاك أعلى من اللازم لتطبيق بسيط هيشتغل على أجهزة عميل قد تكون قديمة.

### الهدف من الـ Rebuild
تطبيق **Native حقيقي** (Qt Widgets)، بنفس الوظائف **100%**، بدون نقصان في أي Feature موجود حاليًا، مع:
- أداء أفضل على الأجهزة الضعيفة/القديمة.
- استقرار بيانات أعلى (قاعدة بيانات حقيقية بدل ملفات JSON متناثرة).
- بنية كود قابلة للاختبار والصيانة (فصل منطق الأعمال عن الواجهة).

---

## 2. التيك ستاك (Tech Stack)

| الطبقة | الاختيار | السبب |
|---|---|---|
| اللغة | Python 3.11+ | نفس لغة المشروع الحالي — إعادة استخدام منطق الحسابات بأقل مخاطرة |
| واجهة المستخدم | **PySide6 (Qt for Python)** | عناصر Native حقيقية، أداء ممتاز على أجهزة قديمة، خفيف الحجم نسبيًا مقارنة بـ Electron |
| قاعدة البيانات | **SQLite** (عبر `sqlalchemy` كـ ORM خفيف، أو `sqlite3` مباشر) | ملف واحد محلي، بدون سيرفر، مناسب 100% لفلسفة "أوفلاين بالكامل"، لكن بعلاقات وسلامة بيانات حقيقية |
| قراءة/كتابة Excel | `openpyxl` (الكتابة والقراءة الحديثة)، `xlrd` (قراءة ملفات `.xls` القديمة القادمة من جهاز البصمة) | نفس المكتبات المستخدمة حاليًا — مُجرَّبة وشغّالة |
| معالجة بيانات | `pandas` | لعرض الجداول (Payroll table, Summary) فقط — مش لتخزين الحالة |
| الرسوم البيانية | `pyqtgraph` أو `QtCharts` (بديل `st.bar_chart`) | Native، بدون متصفح |
| التغليف (Packaging) | `PyInstaller` (`--onefile` أو `--onedir` + installer بسيط) | إخراج exe واحد قابل للتشغيل المباشر على ويندوز |
| الاختبارات | `pytest` لمنطق الأعمال، `pytest-qt` للواجهة | كل Phase (راجع `phases.md`) له اختبارات واضحة |

**قرار حاسم:** منطق الحسابات (تحليل ملفات البصمة، حساب الشيفتات، الرواتب) **يُنقل كما هو تقريبًا** من الكود الحالي (بعد إعادة تنظيمه في وحدات/خدمات)، لأنه مُجرَّب وشغّال. اللي بيتغيّر جذريًا هو **طبقة العرض فقط** وطريقة تخزين البيانات.

---

## 3. أسلوب الأركتيكتشر (Architecture Style)

### مبدأ أساسي: فصل الطبقات (Layered Architecture)

```
┌─────────────────────────────────────────┐
│  UI Layer (PySide6)                      │  ← نوافذ، Widgets، Dialogs
│  - MainWindow, DashboardView, EmployeeDetailView...
└───────────────┬───────────────────────────┘
                │ Signals / Slots (Qt) — لا rerun، تحديث جزئي فقط
┌───────────────▼───────────────────────────┐
│  Controller / ViewModel Layer             │  ← يربط UI بالـ Services
│  - يحتفظ بحالة الشاشة الحالية فقط
└───────────────┬───────────────────────────┘
                │
┌───────────────▼───────────────────────────┐
│  Service / Business Logic Layer          │  ← منطق الأعمال (منقول من app.py)
│  - AttendanceParser (Hikvision / ZK Classic)
│  - PayrollCalculator
│  - CorrectionsEngine
│  - ShiftPatternClassifier
└───────────────┬───────────────────────────┘
                │
┌───────────────▼───────────────────────────┐
│  Data Access Layer (Repository Pattern)  │
│  - CompanyRepository, AttendanceFileRepository,
│    EmployeeRepository, PayrollRepository...
└───────────────┬───────────────────────────┘
                │
┌───────────────▼───────────────────────────┐
│  SQLite Database + ملفات Excel أصلية على القرص │
└─────────────────────────────────────────────┘
```

### قواعد صارمة
1. **الواجهة (UI) لا تحتوي على أي منطق حسابي.** أي دالة زي `calculate_payroll` أو `apply_overrides` تعيش في `services/` وتُختبر بمعزل عن أي Widget.
2. **لا حالة عامة (Global State) متناثرة.** بدل `st.session_state`، تكون فيه كلاس واحد `AppState` (أو ViewModel لكل شاشة) يحتفظ بالحالة الحالية للجلسة، ويُمرَّر بوضوح — مش يتقرأ من متغير عام في كل مكان.
3. **لا Full Re-render.** التحديث يكون جزئي عبر Qt Signals — لو اتصحّح يوم واحد لموظف، بس صف الجدول ده يتحدّث، مش الشاشة كلها.
4. **التخزين معزول تمامًا عن منطق الحسابات.** الـ Repository هو الوحيد اللي "يعرف" إن التخزين SQLite — باقي الكود يتعامل مع Objects/Dataclasses بس.
5. **كل الأكواد والتعليقات وواجهة المستخدم بالعربي** (زي الأصل) — لكن أسماء المتغيرات/الدوال بالإنجليزي كـ Convention.
6. **RTL افتراضي** على مستوى التطبيق كله (`app.setLayoutDirection(Qt.RightToLeft)`).

---

## 4. هيكل المجلدات المقترح

```
attendance_app/
├── main.py                      # نقطة الدخول
├── app_config.py                 # ثوابت (ألوان، أحجام، إعدادات افتراضية)
├── data/
│   └── app.db                    # قاعدة SQLite (تُنشأ تلقائيًا أول تشغيل)
│   └── files/<company>/<year>/<month>/original.xlsx
├── db/
│   ├── models.py                 # تعريف الجداول (SQLAlchemy models)
│   ├── database.py               # الاتصال + migrations بسيطة
│   └── repositories/
│       ├── company_repository.py
│       ├── attendance_repository.py
│       ├── employee_repository.py
│       └── payroll_repository.py
├── services/
│   ├── parsers/
│   │   ├── hikvision_parser.py   # منقول من parse_file_hikvision
│   │   └── zk_classic_parser.py  # منقول من parse_file
│   ├── shift_classifier.py       # assign_shift_patterns, classify_lone_punch
│   ├── corrections_engine.py     # apply_overrides, bulk_smart_apply_all
│   ├── payroll_calculator.py     # calculate_payroll
│   └── excel_exporter.py         # export_to_excel, export_full_file
├── ui/
│   ├── main_window.py
│   ├── widgets/
│   │   ├── file_tree_sidebar.py
│   │   ├── dashboard_view.py
│   │   ├── employee_detail_view.py
│   │   ├── day_editor_dialog.py
│   │   ├── review_panel.py
│   │   └── import_dialog.py
│   └── styles/
│       └── theme.qss             # نفس الألوان الحالية (#cc785c, #efe9de...) كـ QSS
├── tests/
│   ├── test_parsers.py
│   ├── test_payroll_calculator.py
│   ├── test_corrections_engine.py
│   └── fixtures/                 # ملفات إكسل تجريبية حقيقية للـ regression tests
└── packaging/
    └── build.spec                # PyInstaller spec
```

---

## 5. مبادئ التوافق مع النسخة القديمة

- **Regression Testing إلزامي:** أي ملف بصمة كان بيتحلل صح في نسخة Streamlit، لازم ينتج **نفس الأرقام بالظبط** (ساعات العمل، أيام الحضور، الرواتب) في النسخة الجديدة. هنستخدم ملفات حقيقية كـ Fixtures.
- **مفيش تغيير في منطق العمل إلا لو طُلب صراحة.** الهدف الأساسي "Rebuild للواجهة"، مش تغيير قواعد حساب الرواتب.
- **الميزات التالية لازم تتوفر بنفس القوة:**
  - استيراد ملفين بصيغتين مختلفتين (Hikvision + الصيغة القديمة "Att.log report").
  - Redistribute overnight punches + Saturate.
  - نظام التسامح مع المغادرة المبكرة (Tolerance).
  - تصحيح البصمات الناقصة يدويًا (Review Panel) + Day Overrides.
  - Bulk Smart Apply.
  - شجرة ملفات (شركة → سنة → شهر) مع فتح/حذف/إعادة تسمية ( اعادة تسمية الشركة او تغيير الشهر ) 
  - فتح مؤقت (Anonymous) بدون حفظ.
  - تصدير كشف رواتب + ملف كامل (بالتصحيحات) قابل لإعادة الاستيراد.

---

## 6. الملفات المرجعية الأخرى
- `schema.md` — تصميم قاعدة البيانات والعلاقات بين الكيانات.
- `ui.md` — تصميم الشاشات وتجربة الاستخدام.
- `phases.md` — تقسيم مراحل البناء والاختبار.
