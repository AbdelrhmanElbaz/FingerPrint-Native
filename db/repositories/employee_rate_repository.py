# db/repositories/employee_rate_repository.py

import datetime

from db.models import EmployeeRateDefault


class EmployeeRateRepository:
    def __init__(self, session):
        self.session = session

    def get_rate(self, company_id: int, employee_id: int) -> float:
        row = (
            self.session.query(EmployeeRateDefault)
            .filter_by(company_id=company_id, employee_id=employee_id)
            .first()
        )
        return row.hourly_rate if row else 0.0

    def set_rate(self, company_id: int, employee_id: int, hourly_rate: float) -> None:
        """
        يحفظ سعر الساعة كإعداد افتراضي دائم لهذا الموظف داخل شركته — نظير
        employees_defaults.json القديم، لكن كصف قاعدة بيانات حقيقي.
        لا نحفظ قيم صفرية أو سالبة (نفس سلوك save_employee_defaults القديم
        اللي كان بيفلتر {k: v for k, v in rates.items() if v and v > 0}).
        """
        if hourly_rate is None or hourly_rate <= 0:
            return
        row = (
            self.session.query(EmployeeRateDefault)
            .filter_by(company_id=company_id, employee_id=employee_id)
            .first()
        )
        if row:
            row.hourly_rate = hourly_rate
            row.updated_at = datetime.datetime.utcnow()
        else:
            row = EmployeeRateDefault(
                company_id=company_id,
                employee_id=employee_id,
                hourly_rate=hourly_rate,
                updated_at=datetime.datetime.utcnow(),
            )
            self.session.add(row)
        self.session.commit()

    def get_rates_map_by_employee_id(self, company_id: int) -> dict:
        """يرجّع {employee_id: hourly_rate} لكل الأسعار المحفوظة لهذه الشركة."""
        rows = self.session.query(EmployeeRateDefault).filter_by(company_id=company_id).all()
        return {row.employee_id: row.hourly_rate for row in rows}
