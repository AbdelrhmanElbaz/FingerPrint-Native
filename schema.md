# schema.md — تصميم قاعدة البيانات والـ Domain Classes

قاعدة البيانات: **SQLite** (ملف واحد `data/app.db`). الملفات الأصلية (Excel المرفوع من العميل) تُخزَّن كـ ملفات فعلية على القرص، والقاعدة تحتفظ بمسارها فقط (تجنّبًا لتضخيم حجم القاعدة).

---

## 1. مخطط العلاقات (ERD نصّي)

```
Company (1) ──< (N) AttendanceFile
Company (1) ──< (N) Employee
Company (1) ──< (N) EmployeeRateDefault
AttendanceFile (1) ──< (N) AttendanceDay
Employee (1) ──< (N) AttendanceDay
AttendanceDay (1) ──< (N) Punch
AttendanceDay (1) ──< (N) Correction
AttendanceDay (1) ──0..1── DayOverride
AttendanceFile (1) ──0..1── FileSettings
AttendanceFile (1) ──< (N) PayrollExport   (سجل تدقيق للتصدير — اختياري)
```

ملاحظة مهمة: **الموظف مرتبط بالشركة مش بالملف الشهري** — لأن نفس الموظف بيظهر شهر بعد شهر بنفس الـ ID القادم من جهاز البصمة. `AttendanceDay` هو اللي بيربط بين `AttendanceFile` (الشهر) و`Employee` (الموظف).

---

## 2. الجداول (Tables)

### `companies`
| العمود | النوع | ملاحظات |
|---|---|---|
| id | INTEGER PK | |
| name | TEXT UNIQUE NOT NULL | اسم الشركة (زي المجلد الحالي) |
| created_at | DATETIME | |

### `employees`
| العمود | النوع | ملاحظات |
|---|---|---|
| id | INTEGER PK | |
| company_id | INTEGER FK → companies.id | |
| external_code | TEXT NOT NULL | الـ ID القادم من جهاز البصمة (قد يتكرر عبر الشهور لنفس الشخص) |
| name | TEXT | آخر اسم معروف (يتحدّث مع كل استيراد) |
| department | TEXT | |
| UNIQUE(company_id, external_code) | | مفتاح تمييز الموظف داخل شركته |

### `attendance_files` (يمثل "الشهر المفتوح" — نظير `session.json` الحالي)
| العمود | النوع | ملاحظات |
|---|---|---|
| id | INTEGER PK | |
| company_id | INTEGER FK → companies.id (NULL لو Anonymous) | |
| year | INTEGER | |
| month | INTEGER | |
| file_format | TEXT | `hikvision` \| `zk_classic` |
| original_file_path | TEXT | مسار ملف الإكسل الأصلي كما استُلم |
| working_file_path | TEXT | مسار نسخة العمل (تُحدَّث مع كل حفظ) |
| imported_at | DATETIME | |
| is_anonymous | BOOLEAN | فتح مؤقت بدون حفظ دائم |
| UNIQUE(company_id, year, month) | | ملف واحد لكل شهر لكل شركة |

### `attendance_days` (يوم عمل واحد لموظف معيّن في ملف معيّن — نظير عنصر واحد في `emp_days[eid]`)
| العمود | النوع | ملاحظات |
|---|---|---|
| id | INTEGER PK | |
| attendance_file_id | INTEGER FK → attendance_files.id | |
| employee_id | INTEGER FK → employees.id | |
| day_number | INTEGER | 1–31 |
| status | TEXT | `حضور` \| `غياب` |
| total_minutes | INTEGER | دقائق العمل الفعلية (قبل أي Override) |
| incomplete | BOOLEAN | فيه بصمة ناقصة لم تُحل بعد |
| shift_pattern | TEXT NULLABLE | ناتج `assign_shift_patterns` |
| tolerance_added | INTEGER DEFAULT 0 | دقائق أُضيفت بسبب نظام التسامح |
| UNIQUE(attendance_file_id, employee_id, day_number) | | |

### `punches` (كل بصمة خام في اليوم، بالترتيب)
| العمود | النوع | ملاحظات |
|---|---|---|
| id | INTEGER PK | |
| attendance_day_id | INTEGER FK → attendance_days.id | |
| seq_index | INTEGER | ترتيب البصمة داخل اليوم (0, 1, 2...) |
| time_value | TEXT | صيغة `HH:MM` |
| punch_role | TEXT | `check_in` \| `check_out` (مُشتق من الترتيب الزوجي/الفردي) |

> ملاحظة: `punch_pairs` المحسوبة (الفروقات بالدقائق) **لا تُخزَّن** — تُحسب Runtime من `punches` عند الحاجة، لتفادي تكرار مصدر الحقيقة (Source of Truth الوحيد هو البصمات الخام).

### `corrections` (تصحيح بصمة ناقصة واحدة — نظير `st.session_state.corrections[key_base][rev_key]`)
| العمود | النوع | ملاحظات |
|---|---|---|
| id | INTEGER PK | |
| attendance_day_id | INTEGER FK → attendance_days.id | |
| review_index | INTEGER | يقابل `ri` في `needs_review` |
| resolved_time | TEXT | الوقت المُدخَل يدويًا |
| punch_role | TEXT | `check_in` \| `check_out` — هل المُصحَّح هو الحضور أم الانصراف |
| created_at | DATETIME | |
| UNIQUE(attendance_day_id, review_index) | | |

### `day_overrides` (استبدال كامل ليوم معيّن — نظير `day_overrides[key_base]`)
| العمود | النوع | ملاحظات |
|---|---|---|
| id | INTEGER PK | |
| attendance_day_id | INTEGER FK UNIQUE → attendance_days.id | علاقة 1-to-1 |
| status | TEXT | `حضور` \| `غياب` |
| pairs_json | TEXT | JSON لقائمة أزواج (حضور، انصراف) — تُبقى JSON لأنها بيانات مؤقتة قابلة للتعديل الحر |

### `employee_rate_defaults` (نظير `employees_defaults.json`)
| العمود | النوع | ملاحظات |
|---|---|---|
| id | INTEGER PK | |
| company_id | INTEGER FK → companies.id | |
| employee_id | INTEGER FK → employees.id | |
| hourly_rate | REAL | |
| updated_at | DATETIME | |
| UNIQUE(company_id, employee_id) | | |

### `file_settings` (نظير `session_settings.json` — إعدادات الشيفت الخاصة بملف/شهر معيّن)
| العمود | النوع | ملاحظات |
|---|---|---|
| id | INTEGER PK | |
| attendance_file_id | INTEGER FK UNIQUE → attendance_files.id | |
| cutoff_hour | REAL DEFAULT 3.0 | حد Redistribute |
| saturate_minutes | INTEGER NULLABLE | حد Saturate |
| tolerance_enabled | BOOLEAN DEFAULT 0 | |
| tolerance_minutes | INTEGER DEFAULT 0 | |
| duplicate_punch_tolerance | INTEGER DEFAULT 10 | |

### `payroll_exports` (سجل تدقيق اختياري — يُسجّل كل مرة تم فيها تصدير كشف رواتب)
| العمود | النوع | ملاحظات |
|---|---|---|
| id | INTEGER PK | |
| attendance_file_id | INTEGER FK → attendance_files.id | |
| exported_at | DATETIME | |
| export_type | TEXT | `payroll_only` \| `full_complete` |
| total_net_salary | REAL | |
| file_path | TEXT | |

### `app_settings` (Key-Value عامة — نظير `last_company.txt`)
| العمود | النوع | ملاحظات |
|---|---|---|
| key | TEXT PK | مثال: `last_company_id`, `last_year`, `last_month` |
| value | TEXT | |

---

## 3. الـ Domain Classes (طبقة منطق الأعمال — منفصلة عن الـ ORM)

هذه الكلاسات هي اللي بيتعامل معاها `services/` و`ui/` — **مش** كلاسات SQLAlchemy مباشرة، عشان منطق الحسابات يفضل مستقل تمامًا عن قاعدة البيانات (يسهل اختباره بدون DB).

```python
@dataclass
class Punch:
    time: str            # "HH:MM"
    role: Literal["check_in", "check_out"]

@dataclass
class ReviewItem:
    review_index: int
    type: Literal["missing_out", "missing_in"]
    known_time: str
    resolved_time: Optional[str] = None
    punch_role: Literal["check_in", "check_out"] = "check_in"

@dataclass
class AttendanceDay:
    day_number: int
    status: Literal["حضور", "غياب"]
    total_minutes: int
    incomplete: bool
    punches: list[Punch]
    needs_review: list[ReviewItem]
    shift_pattern: Optional[str] = None
    tolerance_added: int = 0
    override: Optional["DayOverride"] = None

@dataclass
class DayOverride:
    status: Literal["حضور", "غياب"]
    pairs: list[tuple[str, str]]   # [(check_in, check_out), ...]

@dataclass
class Employee:
    id: int
    external_code: str
    name: str
    department: str

@dataclass
class AttendanceFile:
    id: int
    company_id: Optional[int]
    year: int
    month: int
    file_format: Literal["hikvision", "zk_classic"]
    is_anonymous: bool
    settings: "FileSettings"

@dataclass
class FileSettings:
    cutoff_hour: float = 3.0
    saturate_minutes: Optional[int] = None
    tolerance_enabled: bool = False
    tolerance_minutes: int = 0
    duplicate_punch_tolerance: int = 10

@dataclass
class PayrollRow:
    employee_id: int
    name: str
    department: str
    attendance_days: float
    absent_days: int
    incomplete_days: int
    work_hours: float
    hourly_rate: float
    net_salary: float
```

**قاعدة:** الخدمات (`PayrollCalculator`, `CorrectionsEngine`, `AttendanceParser`) تستقبل وتُرجع هذه الـ Dataclasses فقط. الـ Repository هو الوحيد المسؤول عن التحويل من/إلى صفوف SQLite.

---

## 4. ملاحظات هامة على الترحيل من النسخة الحالية

1. **`raw_times` الحالية** (قائمة نصوص خام) هتتفكك لصفوف في `punches` — بيسهّل الاستعلام لاحقًا (مثلاً: "كل البصمات المتأخرة في يوم كذا") بدل تحليل JSON كل مرة.
2. **`corrections` بمفاتيح نصية (`f"{eid}_{di}"`)** الحالية هتتحول لعلاقات FK حقيقية (`attendance_day_id`) — أوضح وأقل عرضة للأخطاء.
3. **الملف الأصلي (`_original.bin`)** يفضل يتخزن كملف على القرص زي ما هو دلوقتي (مش BLOB في القاعدة) — قواعد SQLite مش مُحسَّنة لتخزين ملفات كبيرة.
4. **الترحيل من بيانات قديمة (إن وُجدت):** إسكريبت `migrate_legacy_json_to_sqlite.py` لمرة واحدة، يقرأ مجلدات `data/<company>/<year>/<month>/*.json` الحالية ويحوّلها لصفوف SQLite — يُشغَّل تلقائيًا أول تشغيل للنسخة الجديدة لو لقى بيانات قديمة.
