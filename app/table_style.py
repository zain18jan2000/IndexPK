from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView

TABLE_QSS = """
QTableView {
    background: #ffffff;
    alternate-background-color: #f5f8f7;
    color: #1f2937;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    gridline-color: transparent;
    selection-background-color: #d6efe3;
    selection-color: #0f3d2e;
    outline: 0;
}
QTableView::item {
    padding: 6px 12px;
    border: none;
}
QTableView::item:hover {
    background: #e9f4ef;
}
QHeaderView::section {
    background: #f9fafb;
    color: #374151;
    font-weight: 600;
    padding: 10px 12px;
    border: none;
    border-bottom: 2px solid #d1d5db;
}
"""

SCROLLBAR_QSS = """
QScrollBar:vertical {
    background: transparent;
    width: 12px;
    margin: 4px 2px 4px 0;
    border: none;
}
QScrollBar::handle:vertical {
    background: #c9d1d9;
    border-radius: 4px;
    min-height: 36px;
}
QScrollBar::handle:vertical:hover   { background: #9fb0a8; }
QScrollBar::handle:vertical:pressed { background: #0f766e; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px; width: 0px; background: none; border: none;
}
QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {
    background: none; width: 0px; height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}

QScrollBar:horizontal {
    background: transparent;
    height: 12px;
    margin: 0 4px 2px 4px;
    border: none;
}
QScrollBar::handle:horizontal {
    background: #c9d1d9;
    border-radius: 4px;
    min-width: 36px;
}
QScrollBar::handle:horizontal:hover { background: #9fb0a8; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    height: 0px; width: 0px; background: none; border: none;
}
QScrollBar::left-arrow:horizontal, QScrollBar::right-arrow:horizontal {
    background: none; width: 0px; height: 0px;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}
"""

# Fixed column widths (px) for the narrow columns
COL_WIDTHS = {0: 120, 3: 140, 4: 120}                     # constituents
PORTFOLIO_COL_WIDTHS = {0: 120, 2: 130, 3: 130, 4: 170}   # portfolio


def _apply_base_table_style(view: QTableView) -> None:
    view.setStyleSheet(TABLE_QSS)
    view.verticalScrollBar().setStyleSheet(SCROLLBAR_QSS)
    view.horizontalScrollBar().setStyleSheet(SCROLLBAR_QSS)

    view.setAlternatingRowColors(True)
    view.setShowGrid(False)
    view.setSelectionBehavior(QAbstractItemView.SelectRows)
    view.setSelectionMode(QAbstractItemView.SingleSelection)
    view.setEditTriggers(QAbstractItemView.NoEditTriggers)
    view.setMouseTracking(True)
    view.setWordWrap(False)
    view.setTextElideMode(Qt.ElideRight)
    view.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

    view.verticalHeader().setVisible(False)
    view.verticalHeader().setDefaultSectionSize(36)

    header = view.horizontalHeader()
    header.setHighlightSections(False)
    header.setStretchLastSection(False)
    header.setSectionResizeMode(QHeaderView.Fixed)


def style_constituents_table(view: QTableView) -> None:
    _apply_base_table_style(view)
    header = view.horizontalHeader()
    for col, width in COL_WIDTHS.items():
        header.resizeSection(col, width)
    header.setSectionResizeMode(1, QHeaderView.Stretch)            # Company
    header.setSectionResizeMode(2, QHeaderView.ResizeToContents)   # Sector


def style_portfolio_table(view: QTableView) -> None:
    _apply_base_table_style(view)
    header = view.horizontalHeader()
    for col, width in PORTFOLIO_COL_WIDTHS.items():
        header.resizeSection(col, width)
    header.setSectionResizeMode(1, QHeaderView.Stretch)            # Company