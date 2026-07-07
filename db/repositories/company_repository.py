# db/repositories/company_repository.py

from db.models import Company
from services.paths import delete_company_folder, get_company_dir


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
        """
        يغيّر اسم الشركة في القاعدة، ويعيد تسمية مجلدها الفعلي على القرص
        كمان (data/<old_name>/ → data/<new_name>/) — لأن كل مسارات الملفات
        (working/original) محسوبة بناءً على اسم الشركة، فلو المجلد ما
        اتغيّرش اسمه بعد إعادة التسمية، الملفات القديمة تصبح غير قابلة
        للوصول (يدور عليها البرنامج بالاسم الجديد فما يلاقيهاش).
        يرجّع False لو الاسم الجديد مستخدم بالفعل.
        """
        if self.get_by_name(new_name):
            return False
        company = self.get_by_id(company_id)
        if not company:
            return False

        old_name = company.name
        old_dir = get_company_dir(old_name)
        new_dir = get_company_dir(new_name)

        if old_dir.exists() and new_dir.exists():
            # لو المجلد الجديد موجود بالفعل بالصدفة (بدون سجل شركة مطابق) — لا نخاطر بدمجهم
            return False

        company.name = new_name
        self.session.commit()

        try:
            if old_dir.exists():
                old_dir.rename(new_dir)
        except Exception:
            # لو فشلت إعادة تسمية المجلد لأي سبب (قفل ملف مفتوح مثلاً)،
            # نتراجع عن التغيير في القاعدة عشان نفضل متزامنين
            company.name = old_name
            self.session.commit()
            return False

        return True

    def delete(self, company_id: int) -> None:
        """
        يحذف الشركة من قاعدة البيانات (بكل ما يتبعها من ملفات/موظفين لو
        العلاقات معرَّفة بـ cascade)، ثم يحذف مجلدها بالكامل فعليًا من
        القرص (data/<company>/) — بدون هذه الخطوة، مجلد الشركة وكل
        ملفاتها تفضل موجودة على القرص رغم اختفائها من الشجرة.
        """
        company = self.get_by_id(company_id)
        if not company:
            return
        company_name = company.name

        self.session.delete(company)
        self.session.commit()

        delete_company_folder(company_name)
