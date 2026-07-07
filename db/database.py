# db/database.py
# إدارة الاتصال بـ SQLite + إنشاء الجداول تلقائيًا أول تشغيل.
# ملاحظة: لا حاجة لأي تثبيت أو سيرفر خارجي — SQLite ملف واحد على القرص.

import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base


def _get_data_root() -> Path:
    """
    نفس منطق _get_data_root في الكود الأصلي: لو البرنامج مُغلَّف كـ exe
    (PyInstaller/frozen)، نستخدم مجلد الـ exe نفسه. غير كده، مجلد المشروع.
    """
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent.parent
    root = base / "data"
    root.mkdir(exist_ok=True)
    return root


DB_PATH = _get_data_root() / "app.db"
_engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)


def init_db():
    """ينشئ كل الجداول لو مش موجودة بالفعل (Migration بسيطة — بدون Alembic في المرحلة دي)."""
    Base.metadata.create_all(_engine)


def get_session():
    """يرجّع جلسة (Session) جديدة للتعامل مع القاعدة."""
    return SessionLocal()
