# ui/widgets/file_tree_sidebar.py
# ويدجت شجرة الملفات (شركة → سنة → شهر) — بديل الـ Sidebar الحالي في Streamlit.
# يعرض شجرة قابلة للطي/الفتح مع قائمة سياقية (Right-click) لكل عنصر: فتح / حذف / إعادة تسمية.
#
# يعتمد على:
#   CompanyRepository.list_all() -> list[Company]
#   CompanyRepository.rename(company_id, new_name) -> bool
#   CompanyRepository.delete(company_id) -> None
#   AttendanceFileRepository.list_tree_by_company(company_id) -> dict[int, list[int]]
#   AttendanceFileRepository.get_by_company_year_month(company_id, year, month) -> AttendanceFile | None
#   AttendanceFileRepository.delete(file_id) -> None

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QMenu,
    QInputDialog, QMessageBox, QLineEdit
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction

ARABIC_MONTHS = [
    '', 'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
    'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'
]

# ── أنواع العناصر في الشجرة (نخزنها في UserRole للتمييز عند الضغط) ──────
NODE_COMPANY = "company"
NODE_YEAR    = "year"
NODE_MONTH   = "month"


class FileTreeSidebar(QWidget):
    """
    ويدجت شجرة الملفات. يُستخدم داخل QDockWidget في MainWindow.

    Signals:
        month_opened(company_id: int, company_name: str, year: int, month: int)
            → يُطلق عند الضغط على شهر لفتحه.
        company_renamed(company_id: int, new_name: str)
            → يُطلق بعد نجاح إعادة التسمية (لتحديث عنوان النافذة مثلاً).
        tree_changed()
            → يُطلق بعد أي حذف/إعادة تسمية تؤثر على الشجرة.
    """

    month_opened    = Signal(int, str, int, int)
    company_renamed = Signal(int, str)
    tree_changed    = Signal()

    def __init__(self, company_repo, attendance_repo, parent=None):
        super().__init__(parent)
        self.company_repo    = company_repo
        self.attendance_repo = attendance_repo
        self._current_company_id = None
        self._current_year       = None
        self._current_month      = None

        self._build_ui()
        self.refresh()

    # ──────────────────────────────────────────────────────────────────
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setLayoutDirection(Qt.RightToLeft)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)

        layout.addWidget(self.tree)

    # ──────────────────────────────────────────────────────────────────
    def set_current_open(self, company_id: int, year: int, month: int):
        """يُستدعى من MainWindow بعد فتح ملف — لتعليمه بعلامة 🔵 في الشجرة."""
        self._current_company_id = company_id
        self._current_year       = year
        self._current_month      = month
        self.refresh()

    # ──────────────────────────────────────────────────────────────────
    def refresh(self):
        """إعادة بناء الشجرة بالكامل من قاعدة البيانات."""
        # نحفظ حالة الطي/الفتح الحالية قبل إعادة البناء
        expanded_companies = set()
        expanded_years = set()
        for i in range(self.tree.topLevelItemCount()):
            co_item = self.tree.topLevelItem(i)
            if co_item.isExpanded():
                expanded_companies.add(co_item.data(0, Qt.UserRole + 1))
            for j in range(co_item.childCount()):
                yr_item = co_item.child(j)
                if yr_item.isExpanded():
                    expanded_years.add(
                        (co_item.data(0, Qt.UserRole + 1), yr_item.data(0, Qt.UserRole + 1))
                    )

        self.tree.clear()

        companies = self.company_repo.list_all()
        if not companies:
            placeholder = QTreeWidgetItem(["لا توجد ملفات محفوظة بعد"])
            placeholder.setFlags(Qt.NoItemFlags)
            self.tree.addTopLevelItem(placeholder)
            return

        for company in companies:
            is_current_co = (company.id == self._current_company_id)
            co_label = f"🏢 {company.name}" + (" 🔵" if is_current_co else "")
            co_item = QTreeWidgetItem([co_label])
            co_item.setData(0, Qt.UserRole, NODE_COMPANY)
            co_item.setData(0, Qt.UserRole + 1, company.id)
            co_item.setData(0, Qt.UserRole + 2, company.name)
            self.tree.addTopLevelItem(co_item)

            year_tree = self.attendance_repo.list_tree_by_company(company.id)
            for year in sorted(year_tree.keys(), reverse=True):
                yr_item = QTreeWidgetItem([f"📅 {year}"])
                yr_item.setData(0, Qt.UserRole, NODE_YEAR)
                yr_item.setData(0, Qt.UserRole + 1, year)
                co_item.addChild(yr_item)

                for month in year_tree[year]:
                    is_current_mo = (
                        is_current_co and year == self._current_year and month == self._current_month
                    )
                    mo_name = ARABIC_MONTHS[month]
                    mark = "🔵" if is_current_mo else "📄"
                    mo_label = f"{mark} {mo_name}" + ("  (مفتوح)" if is_current_mo else "")
                    mo_item = QTreeWidgetItem([mo_label])
                    mo_item.setData(0, Qt.UserRole, NODE_MONTH)
                    mo_item.setData(0, Qt.UserRole + 1, month)
                    if is_current_mo:
                        mo_item.setFlags(mo_item.flags() & ~Qt.ItemIsEnabled)
                    yr_item.addChild(mo_item)

                if (company.id, year) in expanded_years:
                    yr_item.setExpanded(True)

            if company.id in expanded_companies or is_current_co:
                co_item.setExpanded(True)

    # ──────────────────────────────────────────────────────────────────
    def _get_company_year_month(self, item: QTreeWidgetItem):
        """يرجع (company_id, company_name, year, month) لأي عنصر شهر."""
        month = item.data(0, Qt.UserRole + 1)
        yr_item = item.parent()
        year = yr_item.data(0, Qt.UserRole + 1)
        co_item = yr_item.parent()
        company_id = co_item.data(0, Qt.UserRole + 1)
        company_name = co_item.data(0, Qt.UserRole + 2)
        return company_id, company_name, year, month

    # ──────────────────────────────────────────────────────────────────
    def _on_item_double_clicked(self, item: QTreeWidgetItem, _col: int):
        node_type = item.data(0, Qt.UserRole)
        if node_type == NODE_MONTH:
            if not (item.flags() & Qt.ItemIsEnabled):
                return  # الشهر المفتوح حالياً — لا داعي لإعادة فتحه
            company_id, company_name, year, month = self._get_company_year_month(item)
            self.month_opened.emit(company_id, company_name, year, month)

    # ──────────────────────────────────────────────────────────────────
    def _on_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None:
            return
        node_type = item.data(0, Qt.UserRole)

        menu = QMenu(self)
        if node_type == NODE_COMPANY:
            action_rename = QAction("✏️ إعادة تسمية", self)
            action_delete = QAction("🗑️ حذف الشركة", self)
            action_rename.triggered.connect(lambda: self._rename_company(item))
            action_delete.triggered.connect(lambda: self._delete_company(item))
            menu.addAction(action_rename)
            menu.addAction(action_delete)

        elif node_type == NODE_MONTH:
            action_open = QAction("📂 فتح", self)
            action_delete = QAction("🗑️ حذف الملف", self)
            action_open.triggered.connect(lambda: self._on_item_double_clicked(item, 0))
            action_delete.triggered.connect(lambda: self._delete_month(item))
            menu.addAction(action_open)
            menu.addAction(action_delete)

        else:
            return  # لا قائمة سياقية لمستوى السنة حالياً

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    # ──────────────────────────────────────────────────────────────────
    def _rename_company(self, item: QTreeWidgetItem):
        company_id = item.data(0, Qt.UserRole + 1)
        old_name = item.data(0, Qt.UserRole + 2)

        new_name, ok = QInputDialog.getText(
            self, "إعادة تسمية الشركة", "الاسم الجديد:",
            QLineEdit.Normal, old_name
        )
        if not ok:
            return
        new_name = new_name.strip().upper()
        if not new_name or new_name == old_name:
            return

        try:
            success = self.company_repo.rename(company_id, new_name)
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشلت إعادة التسمية:\n{e}")
            return

        if not success:
            QMessageBox.warning(self, "تعذّر التنفيذ", "الاسم مستخدم بالفعل أو غير صالح.")
            return

        self.company_renamed.emit(company_id, new_name)
        self.refresh()

    # ──────────────────────────────────────────────────────────────────
    def _delete_company(self, item: QTreeWidgetItem):
        company_id = item.data(0, Qt.UserRole + 1)
        company_name = item.data(0, Qt.UserRole + 2)

        confirm = QMessageBox.warning(
            self, "تأكيد الحذف",
            f"⚠️ سيتم حذف الشركة \"{company_name}\" بكل ملفاتها نهائيًا.\nهذا الإجراء لا يمكن التراجع عنه.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        try:
            self.company_repo.delete(company_id)
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل الحذف:\n{e}")
            return

        if company_id == self._current_company_id:
            self._current_company_id = None
            self._current_year = None
            self._current_month = None

        self.tree_changed.emit()
        self.refresh()

    # ──────────────────────────────────────────────────────────────────
    def _delete_month(self, item: QTreeWidgetItem):
        company_id, company_name, year, month = self._get_company_year_month(item)
        mo_name = ARABIC_MONTHS[month]

        confirm = QMessageBox.warning(
            self, "تأكيد الحذف",
            f"⚠️ حذف ملف {mo_name} {year} لشركة \"{company_name}\" نهائيًا؟",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        try:
            att_file = self.attendance_repo.get_by_company_year_month(company_id, year, month)
            if att_file:
                self.attendance_repo.delete(att_file.id)
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل الحذف:\n{e}")
            return

        if (company_id == self._current_company_id
                and year == self._current_year and month == self._current_month):
            self._current_company_id = None
            self._current_year = None
            self._current_month = None

        self.tree_changed.emit()
        self.refresh()
