# db/repositories/correction_state_repository.py
# يحفظ ويحمّل حالة التصحيحات (corrections + day_overrides) لكل ملف شهر.
# يستخدم جدول app_settings (key-value) كـ JSON بدل جداول منفصلة —
# لأن البيانات مؤقتة وقابلة للتغيير الحر، وحجمها صغير نسبيًا.
# يُستدعى من MainWindow فقط — لا تعرفه طبقة الـ UI المباشرة.

import json

from sqlalchemy.orm import Session

from db.models import AppSetting


class CorrectionStateRepository:
    def __init__(self, session: Session):
        self.session = session

    # ── مفاتيح التخزين ────────────────────────────────────────────────
    @staticmethod
    def _corr_key(file_id: int) -> str:
        return f"corrections_file_{file_id}"

    @staticmethod
    def _ov_key(file_id: int) -> str:
        return f"day_overrides_file_{file_id}"

    # ══════════════════════════════════════════════════════════════════
    def save(self, file_id: int, corrections: dict, day_overrides: dict):
        """يحفظ حالة التصحيحات الكاملة لملف معيّن في app_settings."""
        self._upsert(self._corr_key(file_id), json.dumps(corrections, ensure_ascii=False))
        self._upsert(self._ov_key(file_id),   json.dumps(day_overrides, ensure_ascii=False))

    def load(self, file_id: int) -> dict:
        """يُرجع {'corrections': dict, 'day_overrides': dict} — أو قواميس فارغة لو لا يوجد."""
        corr_json = self._fetch(self._corr_key(file_id))
        ov_json   = self._fetch(self._ov_key(file_id))
        try:
            corrections = json.loads(corr_json) if corr_json else {}
        except (json.JSONDecodeError, TypeError):
            corrections = {}
        try:
            day_overrides = json.loads(ov_json) if ov_json else {}
        except (json.JSONDecodeError, TypeError):
            day_overrides = {}
        return {'corrections': corrections, 'day_overrides': day_overrides}

    def delete(self, file_id: int):
        """يحذف حالة التصحيحات المحفوظة لملف معيّن (عند حذف الملف من الشجرة)."""
        for key in (self._corr_key(file_id), self._ov_key(file_id)):
            row = self.session.get(AppSetting, key)
            if row:
                self.session.delete(row)
        self.session.commit()

    # ══════════════════════════════════════════════════════════════════
    def _upsert(self, key: str, value: str):
        row = self.session.get(AppSetting, key)
        if row:
            row.value = value
        else:
            self.session.add(AppSetting(key=key, value=value))
        self.session.commit()

    def _fetch(self, key: str) -> str | None:
        row = self.session.get(AppSetting, key)
        return row.value if row else None
