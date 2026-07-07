# ui/widgets/payroll_table_model.py
# نموذج Qt حقيقي لجدول كشف الرواتب (QAbstractTableModel) — بديل st.dataframe.
# يُستخدم داخل QTableView مباشرة أو عبر QSortFilterProxyModel للبحث/التصفية.

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
import pandas as pd

# أعمدة تُعرض بفواصل عشرية (بقية الأعمدة الرقمية تُعرض كأعداد صحيحة)
_DECIMAL_COLUMNS = {'سعر الساعة', 'صافي الراتب', 'ساعات العمل الفعلية', 'أيام الحضور'}


class PayrollTableModel(QAbstractTableModel):
    def __init__(self, df: pd.DataFrame | None = None, parent=None):
        super().__init__(parent)
        self._df = df if df is not None else pd.DataFrame()

    def set_dataframe(self, df: pd.DataFrame):
        self.beginResetModel()
        self._df = df.reset_index(drop=True)
        self.endResetModel()

    def dataframe(self) -> pd.DataFrame:
        return self._df

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._df)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._df.columns)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid() or self._df.empty:
            return None
        col_name = self._df.columns[index.column()]
        value = self._df.iat[index.row(), index.column()]

        if role in (Qt.DisplayRole, Qt.EditRole):
            if isinstance(value, (int, float)):
                if col_name in _DECIMAL_COLUMNS:
                    return f"{value:,.2f}" if col_name != 'أيام الحضور' else f"{value:,.1f}"
                return f"{int(value):,}"
            return str(value)

        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignCenter)

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return str(self._df.columns[section])
        return str(section + 1)

    def sort(self, column: int, order=Qt.AscendingOrder):
        if self._df.empty:
            return
        col_name = self._df.columns[column]
        self.layoutAboutToBeChanged.emit()
        self._df = self._df.sort_values(
            by=col_name, ascending=(order == Qt.AscendingOrder), kind="mergesort"
        ).reset_index(drop=True)
        self.layoutChanged.emit()
