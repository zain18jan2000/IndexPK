"""Table models for the constituents and portfolio views."""
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


def weight_value(row: dict) -> float:
    """Parse the numeric weight out of a scraped row ('12.09%' -> 12.09)."""
    try:
        return float(str(row.get("Weight", "0")).replace("%", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


# Backwards-compat alias for anyone importing the old name
_weight_value = weight_value


class ConstituentsModel(QAbstractTableModel):
    COLUMNS = ["Ticker", "Company", "Sector", "Price", "Weight"]

    def __init__(self):
        super().__init__()
        self._rows: list[dict] = []

    def set_rows(self, rows: list[dict]) -> None:
        self.beginResetModel()
        # Sort by weight descending so "top N" is simply the first N rows.
        self._rows = sorted(rows, key=weight_value, reverse=True)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.COLUMNS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        col = self.COLUMNS[index.column()]
        if role == Qt.DisplayRole:
            return row.get(col, "")
        if role == Qt.TextAlignmentRole:
            if col in ("Price", "Weight"):
                return int(Qt.AlignRight | Qt.AlignVCenter)
            return int(Qt.AlignLeft | Qt.AlignVCenter)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.COLUMNS[section]
        return None


class PortfolioModel(QAbstractTableModel):
    """Rows are pre-computed allocation dicts (see PortfolioTab.populate)."""
    COLUMNS = ["Ticker", "Company", "Weight", "Allocation %", "Amount (PKR)"]

    def __init__(self):
        super().__init__()
        self._rows: list[dict] = []
        self._index_name: str = ""

    def set_index_name(self, name: str) -> None:
        self._index_name = name
        # The Weight header is dynamic ("KMI-30 Weight" / "KSE-100 Weight")
        self.headerDataChanged.emit(Qt.Horizontal, 2, 2)

    def set_rows(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def clear(self) -> None:
        self.set_rows([])

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.COLUMNS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        col = self.COLUMNS[index.column()]

        if role == Qt.DisplayRole:
            val = row.get(col, "")
            if col == "Amount (PKR)":
                try:
                    return f"{float(val):,.2f}"
                except (TypeError, ValueError):
                    return val
            if col == "Allocation %":
                try:
                    return f"{float(val):.2f}%"
                except (TypeError, ValueError):
                    return val
            return val

        if role == Qt.TextAlignmentRole:
            if col in ("Weight", "Allocation %", "Amount (PKR)"):
                return int(Qt.AlignRight | Qt.AlignVCenter)
            return int(Qt.AlignLeft | Qt.AlignVCenter)

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            if section == 2 and self._index_name:
                return f"{self._index_name} Weight"
            return self.COLUMNS[section]
        return None