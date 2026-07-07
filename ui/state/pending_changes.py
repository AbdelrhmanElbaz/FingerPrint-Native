# ui/state/pending_changes.py
# كلاس بسيط لإدارة التعديلات المعلَّقة (Pending Changes) —
# بديل نظيف لـ st.session_state['pending_changes'] في oldapp.py.
# لا يعتمد على أي Widget — يمكن اختباره بمعزل تام.


class PendingChangesStore:
    """
    يخزن التعديلات المعلَّقة (لم تُطبَّق بعد على corrections/day_overrides الفعلية).

    كل تعديل له مفتاح فريد (str) وبيانات (dict) تصف نوع التعديل:
      - type='correction'    → تصحيح بصمة ناقصة
      - type='day_override'  → استبدال يوم كامل
      - type='remove_override' → إزالة استبدال يوم
    """

    def __init__(self):
        self._store: dict[str, dict] = {}

    def add(self, key: str, data: dict):
        """يضيف أو يُحدّث تعديلًا معلَّقًا."""
        self._store[key] = data

    def remove(self, key: str):
        """يحذف تعديلًا معلَّقًا (لو كان موجودًا)."""
        self._store.pop(key, None)

    def get_all(self) -> dict:
        """يرجع نسخة من كل التعديلات المعلَّقة."""
        return dict(self._store)

    def count(self) -> int:
        """عدد التعديلات المعلَّقة الحالية."""
        return len(self._store)

    def clear(self):
        """يمسح كل التعديلات المعلَّقة."""
        self._store.clear()

    def has(self, key: str) -> bool:
        return key in self._store
