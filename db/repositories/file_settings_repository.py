# db/repositories/file_settings_repository.py

from db.models import FileSettings


class FileSettingsRepository:
    def __init__(self, session):
        self.session = session

    def get_by_file(self, attendance_file_id: int) -> FileSettings | None:
        return (
            self.session.query(FileSettings)
            .filter_by(attendance_file_id=attendance_file_id)
            .first()
        )

    def get_or_create(self, attendance_file_id: int) -> FileSettings:
        """
        احتياطي: AttendanceFileRepository.create() بينشئ صف FileSettings
        تلقائيًا مع كل ملف جديد، فده نادرًا ما هيتنفّذ — لكنه بيحمي من أي
        سيناريو (مثلاً بيانات قديمة تم ترحيلها بدون إعدادات).
        """
        settings = self.get_by_file(attendance_file_id)
        if settings:
            return settings
        settings = FileSettings(attendance_file_id=attendance_file_id)
        self.session.add(settings)
        self.session.commit()
        self.session.refresh(settings)
        return settings

    def update(self, attendance_file_id: int, **fields) -> FileSettings | None:
        """
        يحدّث حقول محددة فقط، مثال:
            update(file_id, cutoff_hour=3.5, saturate_minutes=60)
        الحقول المتاحة: cutoff_hour, saturate_minutes, tolerance_enabled,
        tolerance_minutes, duplicate_punch_tolerance.

        مُضاف الآن كأساس جاهز — الواجهة الفعلية لتغييره (Sliders) هتُبنى
        في Phase 8 حسب phases.md.
        """
        settings = self.get_or_create(attendance_file_id)
        for key, value in fields.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
        self.session.commit()
        self.session.refresh(settings)
        return settings
