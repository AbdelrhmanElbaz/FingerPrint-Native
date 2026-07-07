# ui/widgets/dashboard_view.py
# الشاشة الرئيسية / لوحة التحكم (Phase 4) — نظير قسم "الشاشة الرئيسية" في
# ui.md §3.3. لا تتعامل مع قاعدة البيانات مباشرة: تستقبل بيانات جاهزة من
# MainWindow (df, overrides_summary, hourly_rates) وتُطلق Signals عند أي
# تفاعل (تغيير سعر ساعة، طلب فتح تفاصيل موظف) ليتولّاها MainWindow.
#
# ⚠️ لا يوجد هنا أي تصحيح يدوي أو Day Override — دي هتُضاف في Phase 5
# (EmployeeDetailView + corrections_engine) حسب phases.md.

import pandas as pd

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame,
    QLineEdit, QDoubleSpinBox, QPushButton, QTableView, QHeaderView,
    QCheckBox, QTabWidget, QScrollArea
)
from PySide6.QtCore import Qt, Signal, QSortFilterProxyModel
from PySide6.QtCharts import (
    QChart, QChartView, QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis
)

from services.payroll_calculator import calculate_payroll
from ui.widgets.payroll_table_model import PayrollTableModel


class KpiCard(QFrame):
    """كارت مؤشر واحد — نظير [data-testid="stMetric"] في النسخة القديمة."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("kpiCard")
        self.setStyleSheet(
            "#kpiCard { background:#efe9de; border:1px solid #e6dfd8; border-radius:12px; }"
            "#kpiCard QLabel { border: none; }"
        )
        layout = QVBoxLayout(self)
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color:#6c6a64; font-size:11px; font-weight:600;")
        self.value_label = QLabel("—")
        self.value_label.setStyleSheet("color:#141413; font-size:22px; font-weight:700;")
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: str):
        self.value_label.setText(value)


class RateFilterProxy(QSortFilterProxyModel):
    """
    تصفية بالاسم/الـ ID + حد أدنى/أقصى للراتب — بديل الفلترة اليدوية على
    pandas في النسخة القديمة (st_col1 search + mn_col/mx_col).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_text = ""
        self._min_salary = 0.0
        self._max_salary = float("inf")
        self.setDynamicSortFilter(True)

    def set_search_text(self, text: str):
        self._search_text = text.strip()
        self.invalidateFilter()

    def set_salary_range(self, min_v: float, max_v: float):
        self._min_salary = min_v
        self._max_salary = max_v
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        if model is None:
            return False
        df = model.dataframe()
        if df.empty or source_row >= len(df):
            return False
        row = df.iloc[source_row]

        if self._search_text:
            haystack = f"{row['الاسم']} {row['ID']}".lower()
            if self._search_text.lower() not in haystack:
                return False

        net = row['صافي الراتب']
        if not (self._min_salary <= net <= self._max_salary):
            return False

        return True


class DashboardView(QWidget):
    rate_changed = Signal(str, float)   # (external_code, new_rate) → يتولى MainWindow حفظه
    employee_selected = Signal(str)     # (external_code) → Phase 5 (EmployeeDetailView)

    RATE_GRID_COLS = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self._df = pd.DataFrame()
        self._overrides_summary = {}
        self._hourly_rates = {}
        self._rate_inputs = {}

        self._build_ui()

    # ══════════════════════════════════════════════════════════════════
    def _build_ui(self):
        outer = QVBoxLayout(self)

        self.header_label = QLabel("")
        self.header_label.setAlignment(Qt.AlignCenter)
        self.header_label.setStyleSheet("font-size:16px; font-weight:700; padding:6px 0;")
        outer.addWidget(self.header_label)

        # ── قسم أسعار الساعة ──
        rates_box = QFrame()
        rates_layout = QVBoxLayout(rates_box)
        rates_title = QLabel("💰 سعر الساعة لكل موظف")
        rates_title.setStyleSheet("font-weight:600;")
        rates_layout.addWidget(rates_title)

        self.show_all_checkbox = QCheckBox("عرض الموظفين الغائبين كل الشهر أيضًا")
        self.show_all_checkbox.stateChanged.connect(self._refresh_rate_grid)
        rates_layout.addWidget(self.show_all_checkbox)

        self.rates_scroll = QScrollArea()
        self.rates_scroll.setWidgetResizable(True)
        self.rates_scroll.setMaximumHeight(260)
        self.rates_grid_widget = QWidget()
        self.rates_grid = QGridLayout(self.rates_grid_widget)
        self.rates_scroll.setWidget(self.rates_grid_widget)
        rates_layout.addWidget(self.rates_scroll)

        outer.addWidget(rates_box)

        # ── كروت KPI ──
        kpi_row = QHBoxLayout()
        self.kpi_employees = KpiCard("👥 عدد الموظفين")
        self.kpi_total_salary = KpiCard("💵 إجمالي الرواتب")
        self.kpi_total_hours = KpiCard("⏱️ إجمالي ساعات العمل")
        self.kpi_incomplete = KpiCard("⚠️ ببصمات ناقصة")
        for card in (self.kpi_employees, self.kpi_total_salary, self.kpi_total_hours, self.kpi_incomplete):
            kpi_row.addWidget(card)
        outer.addLayout(kpi_row)

        # ── البحث والتصفية ──
        filter_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔎 ابحث عن موظف بالاسم أو الـ ID")
        self.search_input.textChanged.connect(self._on_filter_changed)

        self.min_salary_input = QDoubleSpinBox()
        self.min_salary_input.setRange(0, 10_000_000)
        self.min_salary_input.setPrefix("الحد الأدنى: ")
        self.min_salary_input.valueChanged.connect(self._on_filter_changed)

        self.max_salary_input = QDoubleSpinBox()
        self.max_salary_input.setRange(0, 10_000_000)
        self.max_salary_input.setValue(10_000_000)
        self.max_salary_input.setPrefix("الحد الأقصى: ")
        self.max_salary_input.valueChanged.connect(self._on_filter_changed)

        filter_row.addWidget(self.search_input, 3)
        filter_row.addWidget(self.min_salary_input, 1)
        filter_row.addWidget(self.max_salary_input, 1)
        outer.addLayout(filter_row)

        # ── جدول كشف الرواتب ──
        self.payroll_model = PayrollTableModel()
        self.proxy_model = RateFilterProxy()
        self.proxy_model.setSourceModel(self.payroll_model)

        self.table_view = QTableView()
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSortingEnabled(True)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_view.setSelectionBehavior(QTableView.SelectRows)
        self.table_view.setAlternatingRowColors(True)
        outer.addWidget(self.table_view, 1)

        # ── الرسوم البيانية ──
        self.charts_tabs = QTabWidget()
        self.chart_salary_view = QChartView()
        self.chart_hours_view = QChartView()
        self.charts_tabs.addTab(self.chart_salary_view, "💰 توزيع الرواتب")
        self.charts_tabs.addTab(self.chart_hours_view, "⏱️ ساعات العمل")
        self.charts_tabs.setMaximumHeight(280)
        outer.addWidget(self.charts_tabs)

    # ══════════════════════════════════════════════════════════════════
    def load_data(self, header_text: str, df: pd.DataFrame, overrides_summary: dict, hourly_rates: dict):
        """
        يُستدعى من MainWindow بعد تحليل ملف (استيراد جديد أو فتح من الشجرة).

        df: DataFrame الملخّص من الـ parser (أعمدة: id, name, department,
            work_hours, attendance_days, absent_days, incomplete_days).
        overrides_summary: ناتج services.payroll_calculator.summarize_emp_days()
                           (بعد تطبيق التسامح فقط، بدون تصحيحات يدوية).
        hourly_rates: dict {external_code: rate} — من EmployeeRateRepository،
                     أو {} في وضع Anonymous.
        """
        self.header_label.setText(header_text)
        self._df = df if df is not None else pd.DataFrame()
        self._overrides_summary = overrides_summary or {}
        self._hourly_rates = dict(hourly_rates or {})

        self._refresh_rate_grid()
        self._recompute_payroll()

    # ══════════════════════════════════════════════════════════════════
    def _refresh_rate_grid(self):
        while self.rates_grid.count():
            item = self.rates_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._rate_inputs.clear()

        if self._df.empty:
            return

        show_all = self.show_all_checkbox.isChecked()
        rows = self._df if show_all else self._df[self._df['work_hours'] > 0]

        for i, (_, emp) in enumerate(rows.iterrows()):
            eid = str(emp['id'])
            row_i, col_i = divmod(i, self.RATE_GRID_COLS)

            cell = QFrame()
            cell_layout = QVBoxLayout(cell)
            inc_days = emp.get('incomplete_days', 0)
            warn = f"  |  ⚠️ {int(inc_days)} ناقصة" if inc_days > 0 else ""
            info_label = QLabel(
                f"<b>{emp['name']}</b> (ID: {eid})<br>"
                f"🕐 {emp.get('work_hours', 0):.2f}  |  📅 {emp.get('attendance_days', 0)} يوم{warn}"
            )
            cell_layout.addWidget(info_label)

            row_h = QHBoxLayout()
            rate_spin = QDoubleSpinBox()
            rate_spin.setRange(0, 100000)
            rate_spin.setDecimals(2)
            rate_spin.setValue(self._hourly_rates.get(eid, 0.0))
            rate_spin.valueChanged.connect(lambda val, e=eid: self._on_rate_changed(e, val))
            row_h.addWidget(rate_spin)

            view_btn = QPushButton("🔍")
            view_btn.setFixedWidth(32)
            view_btn.setToolTip("فتح تفاصيل الموظف (Phase 5)")
            view_btn.clicked.connect(lambda _checked=False, e=eid: self.employee_selected.emit(e))
            row_h.addWidget(view_btn)

            cell_layout.addLayout(row_h)
            self.rates_grid.addWidget(cell, row_i, col_i)
            self._rate_inputs[eid] = rate_spin

    # ══════════════════════════════════════════════════════════════════
    def _on_rate_changed(self, eid: str, value: float):
        self._hourly_rates[eid] = value
        self.rate_changed.emit(eid, value)
        self._recompute_payroll()

    # ══════════════════════════════════════════════════════════════════
    def _recompute_payroll(self):
        payroll_df = calculate_payroll(self._df, self._hourly_rates, self._overrides_summary)
        self.payroll_model.set_dataframe(payroll_df)
        self._update_kpis(payroll_df)
        self._update_charts(payroll_df)

    # ══════════════════════════════════════════════════════════════════
    def _update_kpis(self, payroll_df: pd.DataFrame):
        if payroll_df.empty:
            self.kpi_employees.set_value("0")
            self.kpi_total_salary.set_value("0")
            self.kpi_total_hours.set_value("0")
            self.kpi_incomplete.set_value("0")
            return
        self.kpi_employees.set_value(str(len(payroll_df)))
        self.kpi_total_salary.set_value(f"{payroll_df['صافي الراتب'].sum():,.2f}")
        self.kpi_total_hours.set_value(f"{payroll_df['ساعات العمل الفعلية'].sum():,.1f}")
        self.kpi_incomplete.set_value(str(int((payroll_df['أيام بصمة ناقصة'] > 0).sum())))

    # ══════════════════════════════════════════════════════════════════
    def _update_charts(self, payroll_df: pd.DataFrame):
        top_df = payroll_df.sort_values('صافي الراتب', ascending=False).head(15)
        self.chart_salary_view.setChart(self._make_bar_chart(top_df, 'صافي الراتب', "توزيع الرواتب (أعلى 15)"))
        self.chart_hours_view.setChart(self._make_bar_chart(top_df, 'ساعات العمل الفعلية', "ساعات العمل (أعلى 15)"))

    def _make_bar_chart(self, df: pd.DataFrame, value_col: str, title: str) -> QChart:
        chart = QChart()
        chart.setTitle(title)
        if df.empty:
            return chart

        bar_set = QBarSet(value_col)
        bar_set.append([float(v) for v in df[value_col].tolist()])
        series = QBarSeries()
        series.append(bar_set)
        chart.addSeries(series)

        axis_x = QBarCategoryAxis()
        axis_x.append(df['الاسم'].tolist())
        chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        max_val = float(df[value_col].max()) if not df.empty else 1.0
        axis_y.setRange(0, max_val * 1.15 if max_val > 0 else 1.0)
        chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)

        chart.legend().setVisible(False)
        return chart

    # ══════════════════════════════════════════════════════════════════
    def _on_filter_changed(self):
        self.proxy_model.set_search_text(self.search_input.text())
        self.proxy_model.set_salary_range(
            self.min_salary_input.value(), self.max_salary_input.value()
        )
