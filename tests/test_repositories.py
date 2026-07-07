# tests/test_repositories.py
# اختبارات Phase 1: التأكد من أن Repositories الأساسية شغّالة صح.
# التشغيل: pytest tests/test_repositories.py -v

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base
from db.repositories.company_repository import CompanyRepository
from db.repositories.employee_repository import EmployeeRepository
from db.repositories.attendance_repository import AttendanceFileRepository


@pytest.fixture
def session():
    """قاعدة بيانات مؤقتة في الذاكرة (In-Memory) لكل اختبار — لا تلمس data/app.db الحقيقية."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def test_create_and_get_company(session):
    repo = CompanyRepository(session)
    company = repo.create("شركة تجريبية")
    assert company.id is not None
    fetched = repo.get_by_name("شركة تجريبية")
    assert fetched.id == company.id


def test_create_company_is_idempotent(session):
    repo = CompanyRepository(session)
    c1 = repo.create("شركة أ")
    c2 = repo.create("شركة أ")  # نفس الاسم مرة تانية
    assert c1.id == c2.id
    assert len(repo.list_all()) == 1


def test_rename_company(session):
    repo = CompanyRepository(session)
    company = repo.create("اسم قديم")
    ok = repo.rename(company.id, "اسم جديد")
    assert ok is True
    assert repo.get_by_name("اسم جديد") is not None
    assert repo.get_by_name("اسم قديم") is None


def test_rename_company_conflict(session):
    repo = CompanyRepository(session)
    repo.create("شركة موجودة")
    c2 = repo.create("شركة تانية")
    ok = repo.rename(c2.id, "شركة موجودة")  # اسم مستخدم بالفعل
    assert ok is False


def test_delete_company(session):
    repo = CompanyRepository(session)
    company = repo.create("هتتحذف")
    repo.delete(company.id)
    assert repo.get_by_id(company.id) is None


def test_get_or_create_employee(session):
    company_repo = CompanyRepository(session)
    emp_repo = EmployeeRepository(session)

    company = company_repo.create("شركة الموظفين")
    emp1 = emp_repo.get_or_create(company.id, "1001", name="أحمد علي", department="المبيعات")
    assert emp1.id is not None

    # نفس الكود تاني مرة (زي استيراد شهر جديد) — يرجّع نفس السجل، ويحدّث الاسم
    emp2 = emp_repo.get_or_create(company.id, "1001", name="أحمد علي محمد", department="المبيعات")
    assert emp1.id == emp2.id
    assert emp2.name == "أحمد علي محمد"

    all_emps = emp_repo.list_by_company(company.id)
    assert len(all_emps) == 1


def test_create_attendance_file_and_settings(session):
    company_repo = CompanyRepository(session)
    file_repo = AttendanceFileRepository(session)

    company = company_repo.create("شركة الملفات")
    att_file = file_repo.create(
        company_id=company.id, year=2026, month=6, file_format="hikvision"
    )
    assert att_file.id is not None
    assert att_file.settings is not None
    assert att_file.settings.cutoff_hour == 3.0  # القيمة الافتراضية


def test_duplicate_month_same_company_not_allowed(session):
    """نفس الشهر/السنة لنفس الشركة مرتين — لازم يفشل (Unique Constraint)."""
    company_repo = CompanyRepository(session)
    file_repo = AttendanceFileRepository(session)

    company = company_repo.create("شركة التكرار")
    file_repo.create(company_id=company.id, year=2026, month=6, file_format="hikvision")

    with pytest.raises(Exception):
        file_repo.create(company_id=company.id, year=2026, month=6, file_format="hikvision")
        session.commit()


def test_list_tree_by_company(session):
    company_repo = CompanyRepository(session)
    file_repo = AttendanceFileRepository(session)

    company = company_repo.create("شركة الشجرة")
    file_repo.create(company_id=company.id, year=2026, month=6, file_format="hikvision")
    file_repo.create(company_id=company.id, year=2026, month=5, file_format="hikvision")
    file_repo.create(company_id=company.id, year=2025, month=12, file_format="hikvision")

    tree = file_repo.list_tree_by_company(company.id)
    assert tree[2026] == [6, 5]  # تنازلي
    assert tree[2025] == [12]


def test_move_file_to_new_month(session):
    company_repo = CompanyRepository(session)
    file_repo = AttendanceFileRepository(session)

    company = company_repo.create("شركة التغيير")
    att_file = file_repo.create(company_id=company.id, year=2026, month=6, file_format="hikvision")

    ok = file_repo.move_to_new_month(att_file.id, 2026, 7)
    assert ok is True
    updated = file_repo.get_by_id(att_file.id)
    assert updated.month == 7


def test_delete_attendance_file(session):
    company_repo = CompanyRepository(session)
    file_repo = AttendanceFileRepository(session)

    company = company_repo.create("شركة الحذف")
    att_file = file_repo.create(company_id=company.id, year=2026, month=6, file_format="hikvision")
    file_repo.delete(att_file.id)
    assert file_repo.get_by_id(att_file.id) is None
