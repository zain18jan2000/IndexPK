from PySide6.QtCore import QLocale, Qt, QThread, Signal, Slot
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDoubleSpinBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QStackedWidget,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.paths import ASSETS_DIR
from app.table_model import ConstituentsModel, PortfolioModel, weight_value
from app.table_style import style_constituents_table, style_portfolio_table
from app.worker import ScrapeWorker

STYLE = """
QMainWindow { background-color: #f4f7f6; }

/* --- Tabs --- */
QTabWidget::pane { border: none; background: transparent; }
QTabBar { background: transparent; }
QTabBar::tab {
    padding: 14px 24px;
    font-size: 14px;
    font-weight: 500;
    color: #84938d;
    background: transparent;
    border: none;
    border-bottom: 3px solid transparent;
    margin-right: 4px;
}
QTabBar::tab:selected { color: #0b6e4f; border-bottom: 3px solid #0b6e4f; }
QTabBar::tab:disabled { color: #c5cdc8; }
QTabBar::tab:hover:!selected:!disabled { color: #16302a; }

/* --- Cards / typography --- */
#card {
    background: #ffffff;
    border: 1px solid #e3e9e6;
    border-radius: 16px;
}
#title    { font-size: 24px; font-weight: 700; color: #16302a; }
#subtitle { font-size: 14px; color: #6b7c75; }
#caption  { font-size: 12px; color: #84938d; }
#footer   { font-size: 11px; color: #9aa8a2; }
#fieldLabel { font-size: 13px; font-weight: 500; color: #16302a; }

/* --- Disclaimer --- */
#disclaimer {
    background: #f9fbfa;
    border: 1px solid #e3e9e6;
    border-radius: 10px;
}
#disclaimerText { font-size: 12px; color: #5a6b64; }

/* --- Amount spin box --- */
QDoubleSpinBox {
    font-size: 22px;
    font-weight: 600;
    color: #16302a;
    padding: 14px 16px;
    border: 1px solid #d3dbd7;
    border-radius: 10px;
    background: #ffffff;
}
QDoubleSpinBox:focus { border: 1px solid #0b6e4f; }
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    width: 0px; height: 0px; border: none;
}

/* --- Slider --- */
QSlider::groove:horizontal {
    height: 6px; background: #e3e9e6; border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: #0b6e4f; border-radius: 3px;
}
QSlider::handle:horizontal {
    width: 20px; height: 20px; margin: -7px 0;
    border-radius: 10px; background: #0b6e4f;
}
QSlider::handle:horizontal:hover { background: #095c41; }
#sliderValue { font-size: 22px; font-weight: 600; color: #0b6e4f; padding: 4px 0; }

/* --- Buttons --- */
QPushButton {
    font-size: 16px;
    font-weight: 600;
    padding: 14px 28px;
    border: none;
    border-radius: 10px;
    background: #0b6e4f;
    color: white;
    min-width: 300px;
}
QPushButton:hover   { background: #095c41; }
QPushButton:pressed { background: #064a34; }
QPushButton:disabled { background: #b8c3be; color: #ffffff; }

#placeholder { font-size: 15px; color: #84938d; }

/* --- Portfolio summary --- */
#totalValue {
    font-size: 22px;
    font-weight: 700;
    color: #0b6e4f;
}
"""

LOGO_WIDTH = 180


# ============================================================
#  Allocation helpers (Tab 4)
# ============================================================
def _sorted_by_weight(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=weight_value, reverse=True)


def _compute_allocations(rows: list[dict], amount: float, num_companies: int) -> list[dict]:
    """Normalise top-N weights to 100%, then scale to PKR amounts.

    Matches the worked example: top 15 sum to 90.18% -> FFC's 12.09 / 90.18
    gives 13.41% of the portfolio, which is PKR 13,406.52 out of 100,000.

    Rounding is corrected so the per-row amounts sum exactly to `amount`
    (largest allocation absorbs the residual paisa).
    """
    top = _sorted_by_weight(rows)[:num_companies]
    weights = [weight_value(r) for r in top]
    total = sum(weights)
    if total <= 0 or amount <= 0:
        return []

    allocations: list[dict] = []
    for r, w in zip(top, weights):
        alloc_pct = (w / total) * 100
        allocations.append({
            "Ticker": r.get("Ticker", ""),
            "Company": r.get("Company", ""),
            "Weight": r.get("Weight", ""),
            "Allocation %": alloc_pct,
            "Amount (PKR)": round(alloc_pct / 100 * amount, 2),
        })

    diff = round(amount - sum(a["Amount (PKR)"] for a in allocations), 2)
    if diff:
        i = max(range(len(allocations)), key=lambda k: allocations[k]["Amount (PKR)"])
        allocations[i]["Amount (PKR)"] = round(allocations[i]["Amount (PKR)"] + diff, 2)

    return allocations


# ============================================================
#  Tab 1 — Pick an Index
# ============================================================
class PickIndexTab(QWidget):
    index_selected = Signal(str)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch(1)
        layout.addLayout(self._build_card_row())
        layout.addSpacing(22)
        layout.addLayout(self._build_disclaimer_row())
        layout.addStretch(1)

    def _build_card_row(self) -> QHBoxLayout:
        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(440)

        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 28))
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(6)

        title = QLabel("Where would you like to invest?")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("Pick an index to see its companies and weights.")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(22)

        self._make_choice(layout, "Invest in KMI-30",
                          "30 largest Shariah-compliant companies", "KMI-30")
        layout.addSpacing(14)
        self._make_choice(layout, "Invest in KSE-100",
                          "Pakistan's headline benchmark index", "KSE-100")

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(card)
        row.addStretch(1)
        return row

    def _make_choice(self, layout, text, caption, index_name):
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumHeight(54)
        btn.clicked.connect(lambda: self.index_selected.emit(index_name))
        layout.addWidget(btn)

        cap = QLabel(caption)
        cap.setObjectName("caption")
        cap.setAlignment(Qt.AlignCenter)
        layout.addWidget(cap)
        return btn

    def _build_disclaimer_row(self) -> QHBoxLayout:
        box = QFrame()
        box.setObjectName("disclaimer")
        box.setFixedWidth(520)

        layout = QVBoxLayout(box)
        layout.setContentsMargins(22, 16, 22, 16)

        text = QLabel(
            "IndexPK suggests how to divide an investment amount across the "
            "constituent companies of a PSX index, based on the latest weights "
            "published by bsl.com.pk. It is intended for long-term, buy-and-hold "
            "investors only.\n\n"
            "This is not financial advice. Returns are never guaranteed — markets "
            "can fall as well as rise. You alone are responsible for your own "
            "investment decisions."
        )
        text.setObjectName("disclaimerText")
        text.setWordWrap(True)
        text.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(text)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(box)
        row.addStretch(1)
        return row


# ============================================================
#  Tab 2 — Investment Amount
# ============================================================
class AmountTab(QWidget):
    amount_submitted = Signal(float)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch(1)
        layout.addLayout(self._build_card_row())
        layout.addStretch(1)

    def _build_card_row(self) -> QHBoxLayout:
        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(440)

        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 28))
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(6)

        title = QLabel("How much would you like to invest?")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        title.setWordWrap(True)

        self.lbl_index = QLabel("")
        self.lbl_index.setObjectName("subtitle")
        self.lbl_index.setAlignment(Qt.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(self.lbl_index)
        layout.addSpacing(22)

        field_lbl = QLabel("Amount (PKR)")
        field_lbl.setObjectName("fieldLabel")
        layout.addWidget(field_lbl)

        self.spin_amount = QDoubleSpinBox()
        self.spin_amount.setLocale(QLocale("en_US"))
        self.spin_amount.setGroupSeparatorShown(True)
        self.spin_amount.setRange(1_000, 1_000_000_000)
        self.spin_amount.setDecimals(0)
        self.spin_amount.setValue(100_000)
        self.spin_amount.setSingleStep(10_000)
        self.spin_amount.setMinimumHeight(56)
        self.spin_amount.setAlignment(Qt.AlignRight)
        layout.addWidget(self.spin_amount)

        layout.addSpacing(18)

        self.btn_calc = QPushButton("Calculate My Allocation")
        self.btn_calc.setCursor(Qt.PointingHandCursor)
        self.btn_calc.setMinimumHeight(54)
        self.btn_calc.clicked.connect(self._submit)
        layout.addWidget(self.btn_calc)

        hint = QLabel("You can come back and change the amount any time.")
        hint.setObjectName("caption")
        hint.setAlignment(Qt.AlignCenter)
        hint.setWordWrap(True)
        layout.addSpacing(10)
        layout.addWidget(hint)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(card)
        row.addStretch(1)
        return row

    def set_index_name(self, name: str) -> None:
        self.lbl_index.setText(f"Investing in {name}")

    def _submit(self) -> None:
        self.amount_submitted.emit(float(self.spin_amount.value()))


# ============================================================
#  Tab 3 — Customize Portfolio
# ============================================================
class ConstituentsTab(QWidget):
    # ScrapeResult, amount, num_companies
    portfolio_ready = Signal(object, float, int)
    scrape_started  = Signal()
    scrape_finished = Signal()

    INDEX_DEFAULTS = {
        "KMI-30":  {"default": 15, "max": 25},
        "KSE-100": {"default": 25, "max": 75},
    }
    MIN_COMPANIES = 7

    def __init__(self):
        super().__init__()
        self._loaded_index: str | None = None
        self._amount: float = 0.0
        self._result = None
        self._thread: QThread | None = None
        self._worker: ScrapeWorker | None = None
        self._model = ConstituentsModel()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 24, 40, 24)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_loading_page())   # 0
        self._stack.addWidget(self._build_error_page())     # 1
        self._stack.addWidget(self._build_content_page())   # 2
        self._stack.setCurrentIndex(0)
        layout.addWidget(self._stack)

    # ---------- page builders ----------
    def _build_loading_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch(1)

        msg = QLabel("Fetching constituents from bsl.com.pk…")
        msg.setObjectName("title")
        msg.setAlignment(Qt.AlignCenter)
        layout.addWidget(msg)

        layout.addSpacing(20)

        bar = QProgressBar()
        bar.setRange(0, 0)
        bar.setTextVisible(False)
        bar.setFixedWidth(400)
        bar.setFixedHeight(8)
        bar.setStyleSheet("""
            QProgressBar { background: #e3e9e6; border: none; border-radius: 4px; }
            QProgressBar::chunk { background: #0b6e4f; border-radius: 4px; }
        """)
        layout.addWidget(bar, alignment=Qt.AlignCenter)

        layout.addSpacing(16)
        hint = QLabel("This usually takes 10–20 seconds.")
        hint.setObjectName("subtitle")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)
        layout.addStretch(1)
        return page

    def _build_error_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch(1)

        icon = QLabel("⚠")
        icon.setStyleSheet("font-size: 48px; color: #d97706;")
        icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon)

        msg = QLabel("Could not fetch data")
        msg.setObjectName("title")
        msg.setAlignment(Qt.AlignCenter)
        layout.addWidget(msg)

        self._error_detail = QLabel("")
        self._error_detail.setObjectName("subtitle")
        self._error_detail.setAlignment(Qt.AlignCenter)
        self._error_detail.setWordWrap(True)
        self._error_detail.setMaximumWidth(640)
        layout.addWidget(self._error_detail, alignment=Qt.AlignCenter)

        layout.addSpacing(20)

        retry = QPushButton("Try Again")
        retry.setCursor(Qt.PointingHandCursor)
        retry.setMinimumHeight(48)
        retry.clicked.connect(self._retry)
        layout.addWidget(retry, alignment=Qt.AlignCenter)

        layout.addStretch(1)
        return page

    def _build_content_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._content_title = QLabel("")
        self._content_title.setObjectName("title")
        layout.addWidget(self._content_title)

        self._as_of_label = QLabel("")
        self._as_of_label.setObjectName("subtitle")
        layout.addWidget(self._as_of_label)
        layout.addSpacing(14)

        table = QTableView()
        table.setModel(self._model)
        table.setMinimumHeight(240)
        style_constituents_table(table)
        layout.addWidget(table, 1)

        layout.addSpacing(20)

        # --- Slider block ------------------------------------------------
        slider_card = QFrame()
        slider_card.setObjectName("card")
        sl = QVBoxLayout(slider_card)
        sl.setContentsMargins(24, 18, 24, 18)
        sl.setSpacing(6)

        q = QLabel("How many companies would you like to invest in?")
        q.setObjectName("fieldLabel")
        q.setAlignment(Qt.AlignCenter)
        sl.addWidget(q)

        self._slider_value = QLabel("")
        self._slider_value.setObjectName("sliderValue")
        self._slider_value.setAlignment(Qt.AlignCenter)
        sl.addWidget(self._slider_value)

        self._slider = QSlider(Qt.Horizontal)
        self._slider.setMinimumHeight(34)
        self._slider.valueChanged.connect(self._update_slider_label)
        sl.addWidget(self._slider)

        self._slider_hint = QLabel("")
        self._slider_hint.setObjectName("caption")
        self._slider_hint.setAlignment(Qt.AlignCenter)
        self._slider_hint.setWordWrap(True)
        sl.addWidget(self._slider_hint)

        layout.addWidget(slider_card)
        layout.addSpacing(16)

        self._btn_build = QPushButton("Build My Portfolio")
        self._btn_build.setCursor(Qt.PointingHandCursor)
        self._btn_build.setMinimumHeight(54)
        self._btn_build.clicked.connect(self._on_build_clicked)
        layout.addWidget(self._btn_build, alignment=Qt.AlignCenter)

        return page

    # ---------- public API ----------
    def is_scraping(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def reset(self) -> None:
        self._loaded_index = None
        self._result = None
        self._stack.setCurrentIndex(0)

    def start_fetch(self, index_name: str, amount: float) -> None:
        self._amount = amount

        if self.is_scraping():
            return

        if self._loaded_index == index_name and self._result is not None:
            self._show_content()
            return

        self._loaded_index = index_name
        self._result = None
        self._stack.setCurrentIndex(0)
        self._kickoff_worker(index_name)

    def shutdown(self) -> None:
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(5_000)

    # ---------- scraping internals ----------
    def _kickoff_worker(self, index_name: str) -> None:
        self._thread = QThread(self)
        self._worker = ScrapeWorker(index_name)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_scrape_finished)
        self._worker.failed.connect(self._on_scrape_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._on_thread_done)

        self._thread.start()
        self.scrape_started.emit()

    def _retry(self) -> None:
        if self._loaded_index is None:
            return
        self._stack.setCurrentIndex(0)
        self._kickoff_worker(self._loaded_index)

    @Slot(object)
    def _on_scrape_finished(self, result) -> None:
        if result.index != self._loaded_index:
            return
        self._result = result
        self._populate_content(result)
        self._stack.setCurrentIndex(2)

    @Slot(str)
    def _on_scrape_failed(self, message: str) -> None:
        self._error_detail.setText(
            "Check your internet connection and try again.\n\n"
            + message.splitlines()[0][:300]
        )
        self._stack.setCurrentIndex(1)

    @Slot()
    def _on_thread_done(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
        if self._thread is not None:
            self._thread.deleteLater()
        self._worker = None
        self._thread = None
        self.scrape_finished.emit()

    # ---------- content population ----------
    def _populate_content(self, result) -> None:
        self._content_title.setText(f"{result.index} — {len(result.rows)} companies")
        self._as_of_label.setText(f"As of {result.as_of}" if result.as_of else "")
        self._model.set_rows(result.rows)

        defaults = self.INDEX_DEFAULTS.get(
            result.index, {"default": 15, "max": 75}
        )
        effective_max = min(defaults["max"], len(result.rows))
        effective_min = min(self.MIN_COMPANIES, effective_max)

        self._slider.blockSignals(True)
        self._slider.setRange(effective_min, effective_max)
        default = max(effective_min, min(defaults["default"], effective_max))
        self._slider.setValue(default)
        self._slider.blockSignals(False)
        self._update_slider_label(default)

        self._slider_hint.setText(
            f"Pick between {effective_min} and {effective_max} companies. "
            "More companies means more diversification, but each position is smaller."
        )

    def _show_content(self) -> None:
        if self._result is not None:
            self._stack.setCurrentIndex(2)

    def _update_slider_label(self, value: int) -> None:
        self._slider_value.setText(f"{value} companies")

    def _on_build_clicked(self) -> None:
        if self._loaded_index is None or self._result is None:
            return
        self.portfolio_ready.emit(
            self._result, self._amount, int(self._slider.value())
        )


# ============================================================
#  Tab 4 — Your Portfolio
# ============================================================
class PortfolioTab(QWidget):
    def __init__(self):
        super().__init__()
        self._model = PortfolioModel()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 24, 40, 24)
        layout.setSpacing(0)

        self._title = QLabel("Your Portfolio")
        self._title.setObjectName("title")
        layout.addWidget(self._title)

        self._subtitle = QLabel("")
        self._subtitle.setObjectName("subtitle")
        layout.addWidget(self._subtitle)
        layout.addSpacing(14)

        self._table = QTableView()
        self._table.setModel(self._model)
        style_portfolio_table(self._table)
        layout.addWidget(self._table, 1)

        note = QLabel(
            "Allocation % re-scales the selected companies' index weights to 100%, "
            "then applies that share to your investment amount."
        )
        note.setObjectName("caption")
        note.setWordWrap(True)
        layout.addSpacing(10)
        layout.addWidget(note)

        layout.addSpacing(10)
        layout.addWidget(self._build_summary_card())

    def _build_summary_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")

        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 22))
        card.setGraphicsEffect(shadow)

        row = QHBoxLayout(card)
        row.setContentsMargins(24, 16, 24, 16)
        row.setSpacing(14)

        left = QLabel("Total to invest")
        left.setObjectName("fieldLabel")

        self._total_value = QLabel("")
        self._total_value.setObjectName("totalValue")

        row.addWidget(left)
        row.addStretch(1)
        row.addWidget(self._total_value)
        return card

    def populate(self, result, amount: float, num_companies: int) -> None:
        allocations = _compute_allocations(result.rows, amount, num_companies)
        self._model.set_index_name(result.index)
        self._model.set_rows(allocations)

        self._subtitle.setText(
            f"{result.index}  ·  {num_companies} companies  ·  "
            f"PKR {amount:,.0f}"
        )
        self._total_value.setText(f"PKR {amount:,.2f}")

    def reset(self) -> None:
        self._model.clear()
        self._model.set_index_name("")
        self._subtitle.setText("")
        self._total_value.setText("")


# ============================================================
#  Main window
# ============================================================
class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("IndexPK — PSX Index Guide")
        self.resize(1000, 760)
        self.setMinimumSize(780, 640)
        self.setStyleSheet(STYLE)

        self._selected_index: str | None = None
        self._amount: float | None = None
        self._num_companies: int | None = None

        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.tab_index        = PickIndexTab()
        self.tab_amount       = AmountTab()
        self.tab_constituents = ConstituentsTab()
        self.tab_portfolio    = PortfolioTab()

        self.tabs.addTab(self.tab_index,        "1. Pick an Index")
        self.tabs.addTab(self.tab_amount,       "2. Investment Amount")
        self.tabs.addTab(self.tab_constituents, "3. Customize Portfolio")
        self.tabs.addTab(self.tab_portfolio,    "4. Your Portfolio")

        for i in (1, 2, 3):
            self.tabs.setTabEnabled(i, False)

        self.tab_index.index_selected.connect(self._on_index_picked)
        self.tab_amount.amount_submitted.connect(self._on_amount_submitted)
        self.tab_constituents.portfolio_ready.connect(self._on_portfolio_ready)
        self.tab_constituents.scrape_started.connect(self._on_scrape_started)
        self.tab_constituents.scrape_finished.connect(self._on_scrape_finished)

        root.addWidget(self.tabs, 1)
        root.addWidget(self._build_footer())

    # ---------- header / footer ----------
    def _build_header(self) -> QWidget:
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(10, 12, 24, 0)

        logo = QLabel()
        pix = QPixmap(str(ASSETS_DIR / "logo.png"))
        if pix.isNull():
            logo.setText("IndexPK")
            logo.setStyleSheet("font-size: 22px; font-weight: 700; color: #0b6e4f;")
        else:
            ratio = self.devicePixelRatioF()
            scaled = pix.scaledToWidth(
                int(LOGO_WIDTH * ratio), Qt.TransformationMode.SmoothTransformation
            )
            scaled.setDevicePixelRatio(ratio)
            logo.setPixmap(scaled)

        layout.addWidget(logo, alignment=Qt.AlignLeft | Qt.AlignTop)
        layout.addStretch(1)
        return header

    def _build_footer(self) -> QLabel:
        footer = QLabel("")
        footer.setObjectName("footer")
        footer.setAlignment(Qt.AlignCenter)
        footer.setContentsMargins(0, 0, 0, 14)
        return footer

    # ---------- flow ----------
    @Slot(str)
    def _on_index_picked(self, index_name: str) -> None:
        changed = self._selected_index != index_name
        self._selected_index = index_name
        self._amount = None
        self._num_companies = None

        self.tab_amount.set_index_name(index_name)
        self.tabs.setTabEnabled(1, True)

        if changed:
            self.tabs.setTabEnabled(2, False)
            self.tabs.setTabEnabled(3, False)
            self.tab_constituents.reset()
            self.tab_portfolio.reset()

        self.tabs.setCurrentIndex(1)

    @Slot(float)
    def _on_amount_submitted(self, amount: float) -> None:
        if self._selected_index is None:
            return
        self._amount = amount
        self.tabs.setTabEnabled(3, False)
        self.tab_portfolio.reset()

        self.tabs.setTabEnabled(2, True)
        self.tabs.setCurrentIndex(2)
        self.tab_constituents.start_fetch(self._selected_index, amount)

    @Slot(object, float, int)
    def _on_portfolio_ready(self, result, amount: float, num: int) -> None:
        self._num_companies = num
        self.tab_portfolio.populate(result, amount, num)
        self.tabs.setTabEnabled(3, True)
        self.tabs.setCurrentIndex(3)

    @Slot()
    def _on_scrape_started(self) -> None:
        self.tabs.setTabEnabled(0, False)
        self.tabs.setTabEnabled(1, False)

    @Slot()
    def _on_scrape_finished(self) -> None:
        self.tabs.setTabEnabled(0, True)
        self.tabs.setTabEnabled(1, True)

    # ---------- shutdown ----------
    def closeEvent(self, event):
        if self.tab_constituents.is_scraping():
            QMessageBox.information(
                self,
                "Please wait",
                "A fetch is still running. Please wait for it to finish before closing.",
            )
            event.ignore()
            return
        self.tab_constituents.shutdown()
        event.accept()