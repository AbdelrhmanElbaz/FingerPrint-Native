# db/repositories/employee_repository.py

from db.models import Employee


class EmployeeRepository:
    def __init__(self, session):
        self.session = session

    def get_or_create(self, company_id: int, external_code: str, name: str = "", department: str = "") -> Employee:
        """
        يبحث عن موظف بنفس الكود الخارجي داخل نفس الشركة. لو موجود، يحدّث
        الاسم/القسم (آخر بيانات معروفة) ويرجّعه. لو مش موجود، يُنشئه.
        """
        emp = (
            self.session.query(Employee)
            .filter_by(company_id=company_id, external_code=external_code)
            .order_by(Employee.id.asc())   # حتمية الاختيار لو فيه صفوف مكررة قديمة
            .first()
        )
        if emp:
            if name:
                emp.name = name
            if department:
                emp.department = department
            self.session.commit()
            return emp

        emp = Employee(
            company_id=company_id,
            external_code=external_code,
            name=name,
            department=department,
        )
        self.session.add(emp)
        self.session.commit()
        self.session.refresh(emp)
        return emp

    def list_by_company(self, company_id: int) -> list[Employee]:
        return self.session.query(Employee).filter_by(company_id=company_id).all()

    def get_by_id(self, employee_id: int) -> Employee | None:
        return self.session.query(Employee).filter_by(id=employee_id).first()
