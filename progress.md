# progress.md

- [Phase 0] بدأنا: هيكل المشروع + main.py + main_window.py + app_config.py + requirements.txt + packaging/build.spec.
- [Phase 0] ✅ نجح: العميل شغّل `python main.py` والنافذة فتحت فعليًا برسالة النجاح. لم يتم تجربة PyInstaller/exe بعد (اختياري، هيتأكد منه في Phase 9).
- [Phase 1] بدأنا: db/models.py (كل الجداول من schema.md) + db/database.py (SQLite + init_db) + CompanyRepository + EmployeeRepository + AttendanceFileRepository + اختبارات tests/test_repositories.py (13 اختبار). main.py بيستدعي init_db() تلقائيًا الآن.
