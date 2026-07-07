# services/paths.py
# نقطة مركزية واحدة لكل ما يخص مسارات مجلد data/ على القرص.
#
# ⚠️ مهم: هذا الملف هو المرجع الوحيد لحساب مسار data/ ومجلدات الشركة/السنة/الشهر.
# أي كود تاني (import_dialog.py، الـ Repositories...) لازم يستخدم الدوال هنا
# بدل ما يعيد حساب المسار بنفسه — عشان نضمن إن كل حاجة بتشاور على نفس المكان
# فعليًا، ولو الملف اتمسح من قاعدة البيانات ينمسح فعليًا من القرص كمان.

import shutil
from pathlib import Path


def get_data_root() -> Path:
    """
    جذر مجلد data/ — بجانب main.py مباشرة (جذر المشروع).
    هذا الملف موجود في <root>/services/paths.py، فـ:
        .resolve().parent  → <root>/services
        .parent (تاني)     → <root>
    """
    root = Path(__file__).resolve().parent.parent / "data"
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_company_dir(company_name: str) -> Path:
    return get_data_root() / company_name


def get_month_dir(company_name: str, year: int, month: int) -> Path:
    return get_company_dir(company_name) / str(year) / f"{month:02d}"


def delete_month_folder(company_name: str, year: int, month: int) -> None:
    """
    يحذف مجلد شهر معيّن (working file + original + أي إعدادات) فعليًا من
    القرص، وينظّف مجلد السنة لو أصبح فاضيًا بعدها.
    نستخدم ignore_errors=True عشان لو المجلد مش موجود أصلاً (مثلاً اتمسح
    يدويًا قبل كده) الحذف من القاعدة ميفشلش بسبب كده.
    """
    month_dir = get_month_dir(company_name, year, month)
    if month_dir.exists():
        shutil.rmtree(month_dir, ignore_errors=True)

    year_dir = get_company_dir(company_name) / str(year)
    try:
        if year_dir.exists() and not any(year_dir.iterdir()):
            year_dir.rmdir()
    except Exception:
        pass


def delete_company_folder(company_name: str) -> None:
    """يحذف مجلد الشركة بالكامل (كل السنوات والشهور جوه) فعليًا من القرص."""
    company_dir = get_company_dir(company_name)
    if company_dir.exists():
        shutil.rmtree(company_dir, ignore_errors=True)
