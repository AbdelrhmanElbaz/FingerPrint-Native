# db/repositories/attendance_repository.py

from db.models import AttendanceFile, FileSettings


class AttendanceFileRepository:
    def __init__(self, session):
        self.session = session

    def create(
        self,
        company_id: int | None,
        year: int,
        month: int,
        file_format: str,
        original_file_path: str = "",
        working_file_path: str = "",
        is_anonymous: bool = False,
    ) -> AttendanceFile:
        att_file = AttendanceFile(
            company_id=company_id,
            year=year,
            month=month,
            file_format=file_format,
            original_file_path=original_file_path,
            working_file_path=working_file_path,
            is_anonymous=is_anonymous,
        )
        self.session.add(att_file)
        self.session.commit()
        self.session.refresh(att_file)

        # إعدادات افتراضية للملف (نظير session_settings.json القديم)
        settings = FileSettings(attendance_file_id=att_file.id)
        self.session.add(settings)
        self.session.commit()

        return att_file

    def get_by_id(self, file_id: int) -> AttendanceFile | None:
        return self.session.query(AttendanceFile).filter_by(id=file_id).first()

    def get_by_company_year_month(self, company_id: int, year: int, month: int) -> AttendanceFile | None:
        return (
            self.session.query(AttendanceFile)
            .filter_by(company_id=company_id, year=year, month=month)
            .first()
        )

    def list_tree_by_company(self, company_id: int) -> dict[int, list[int]]:
        """يرجّع { year: [month, month, ...] } مرتبة تنازليًا — نظير list_company_tree القديمة."""
        files = (
            self.session.query(AttendanceFile)
            .filter_by(company_id=company_id, is_anonymous=False)
            .all()
        )
        tree: dict[int, list[int]] = {}
        for f in files:
            tree.setdefault(f.year, []).append(f.month)
        for year in tree:
            tree[year] = sorted(tree[year], reverse=True)
        return tree

    def delete(self, file_id: int) -> None:
        att_file = self.get_by_id(file_id)
        if att_file:
            self.session.delete(att_file)
            self.session.commit()

    def move_to_new_month(self, file_id: int, new_year: int, new_month: int) -> bool:
        """
        تغيير الشهر/السنة لملف موجود بالفعل (مطلوب صراحة في claude.md ضمن
        ميزات شجرة الملفات). يرجّع False لو فيه ملف تاني بالفعل بنفس الشهر/السنة
        الجديدة لنفس الشركة.
        """
        att_file = self.get_by_id(file_id)
        if not att_file:
            return False
        conflict = self.get_by_company_year_month(att_file.company_id, new_year, new_month)
        if conflict and conflict.id != file_id:
            return False
        att_file.year = new_year
        att_file.month = new_month
        self.session.commit()
        return True
