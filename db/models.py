# db/models.py
# تعريف جداول SQLite طبقًا لـ schema.md — بدون أي منطق أعمال هنا، تعريف بنية فقط.

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text,
    ForeignKey, UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    employees = relationship("Employee", back_populates="company", cascade="all, delete-orphan")
    attendance_files = relationship("AttendanceFile", back_populates="company", cascade="all, delete-orphan")
    rate_defaults = relationship("EmployeeRateDefault", back_populates="company", cascade="all, delete-orphan")


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    external_code = Column(String, nullable=False)  # الـ ID القادم من جهاز البصمة
    name = Column(String)
    department = Column(String)

    company = relationship("Company", back_populates="employees")
    attendance_days = relationship("AttendanceDay", back_populates="employee", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("company_id", "external_code", name="uq_employee_company_code"),)


class AttendanceFile(Base):
    __tablename__ = "attendance_files"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)  # NULL لو Anonymous
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    file_format = Column(String, nullable=False)  # "hikvision" | "zk_classic"
    original_file_path = Column(String)
    working_file_path = Column(String)
    imported_at = Column(DateTime, default=datetime.utcnow)
    is_anonymous = Column(Boolean, default=False)

    company = relationship("Company", back_populates="attendance_files")
    attendance_days = relationship("AttendanceDay", back_populates="attendance_file", cascade="all, delete-orphan")
    settings = relationship("FileSettings", back_populates="attendance_file", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("company_id", "year", "month", name="uq_file_company_year_month"),)


class AttendanceDay(Base):
    __tablename__ = "attendance_days"

    id = Column(Integer, primary_key=True)
    attendance_file_id = Column(Integer, ForeignKey("attendance_files.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    day_number = Column(Integer, nullable=False)
    status = Column(String, nullable=False)  # "حضور" | "غياب"
    total_minutes = Column(Integer, default=0)
    incomplete = Column(Boolean, default=False)
    shift_pattern = Column(String, nullable=True)
    tolerance_added = Column(Integer, default=0)

    attendance_file = relationship("AttendanceFile", back_populates="attendance_days")
    employee = relationship("Employee", back_populates="attendance_days")
    punches = relationship("Punch", back_populates="attendance_day", cascade="all, delete-orphan", order_by="Punch.seq_index")
    corrections = relationship("Correction", back_populates="attendance_day", cascade="all, delete-orphan")
    override = relationship("DayOverride", back_populates="attendance_day", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("attendance_file_id", "employee_id", "day_number", name="uq_day_file_employee_daynum"),
    )


class Punch(Base):
    __tablename__ = "punches"

    id = Column(Integer, primary_key=True)
    attendance_day_id = Column(Integer, ForeignKey("attendance_days.id"), nullable=False)
    seq_index = Column(Integer, nullable=False)
    time_value = Column(String, nullable=False)  # "HH:MM"
    punch_role = Column(String, nullable=False)  # "check_in" | "check_out"

    attendance_day = relationship("AttendanceDay", back_populates="punches")


class Correction(Base):
    __tablename__ = "corrections"

    id = Column(Integer, primary_key=True)
    attendance_day_id = Column(Integer, ForeignKey("attendance_days.id"), nullable=False)
    review_index = Column(Integer, nullable=False)
    resolved_time = Column(String, nullable=False)
    punch_role = Column(String, nullable=False)  # "check_in" | "check_out"
    created_at = Column(DateTime, default=datetime.utcnow)

    attendance_day = relationship("AttendanceDay", back_populates="corrections")

    __table_args__ = (UniqueConstraint("attendance_day_id", "review_index", name="uq_correction_day_review"),)


class DayOverride(Base):
    __tablename__ = "day_overrides"

    id = Column(Integer, primary_key=True)
    attendance_day_id = Column(Integer, ForeignKey("attendance_days.id"), unique=True, nullable=False)
    status = Column(String, nullable=False)
    pairs_json = Column(Text, default="[]")

    attendance_day = relationship("AttendanceDay", back_populates="override")


class EmployeeRateDefault(Base):
    __tablename__ = "employee_rate_defaults"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    hourly_rate = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("Company", back_populates="rate_defaults")

    __table_args__ = (UniqueConstraint("company_id", "employee_id", name="uq_rate_company_employee"),)


class FileSettings(Base):
    __tablename__ = "file_settings"

    id = Column(Integer, primary_key=True)
    attendance_file_id = Column(Integer, ForeignKey("attendance_files.id"), unique=True, nullable=False)
    cutoff_hour = Column(Float, default=3.0)
    saturate_minutes = Column(Integer, nullable=True)
    tolerance_enabled = Column(Boolean, default=False)
    tolerance_minutes = Column(Integer, default=0)
    duplicate_punch_tolerance = Column(Integer, default=10)

    attendance_file = relationship("AttendanceFile", back_populates="settings")


class PayrollExport(Base):
    __tablename__ = "payroll_exports"

    id = Column(Integer, primary_key=True)
    attendance_file_id = Column(Integer, ForeignKey("attendance_files.id"), nullable=False)
    exported_at = Column(DateTime, default=datetime.utcnow)
    export_type = Column(String, nullable=False)  # "payroll_only" | "full_complete"
    total_net_salary = Column(Float, default=0.0)
    file_path = Column(String)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String, primary_key=True)
    value = Column(String)
