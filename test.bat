@echo off
REM تشغيل سكريبت الاختبار على الملف الفعلي
REM ضع هذا الملف في نفس مجلد المشروع (بجانب 1_report-1.xls)

cd /d "%~dp0"
python test_fixture_file.py
pause