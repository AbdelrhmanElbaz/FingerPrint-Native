# db/repositories/company_repository.py

from db.models import Company


class CompanyRepository:
    def __init__(self, session):
        self.session = session

    def list_all(self) -> list[Company]:
        return self.session.query(Company).order_by(Company.name).all()

    def get_by_name(self, name: str) -> Company | None:
        return self.session.query(Company).filter_by(name=name).first()

    def get_by_id(self, company_id: int) -> Company | None:
        return self.session.query(Company).filter_by(id=company_id).first()

    def create(self, name: str) -> Company:
        existing = self.get_by_name(name)
        if existing:
            return existing
        company = Company(name=name)
        self.session.add(company)
        self.session.commit()
        self.session.refresh(company)
        return company

    def rename(self, company_id: int, new_name: str) -> bool:
        """يغيّر اسم الشركة. يرجّع False لو الاسم الجديد مستخدم بالفعل."""
        if self.get_by_name(new_name):
            return False
        company = self.get_by_id(company_id)
        if not company:
            return False
        company.name = new_name
        self.session.commit()
        return True

    def delete(self, company_id: int) -> None:
        company = self.get_by_id(company_id)
        if company:
            self.session.delete(company)
            self.session.commit()
