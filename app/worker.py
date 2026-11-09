"""Background worker that runs Playwright without blocking the Qt UI."""
import traceback

from PySide6.QtCore import QObject, Signal, Slot


class ScrapeWorker(QObject):
    progress = Signal(str)
    finished = Signal(object)   # emits a ScrapeResult
    failed   = Signal(str)      # emits full traceback

    def __init__(self, index_name: str):
        super().__init__()
        self._index_name = index_name

    @Slot()
    def run(self) -> None:
        try:
            self.progress.emit(f"Opening bsl.com.pk for {self._index_name}…")
            from scraper.psx_index_scraper import scrape_index
            result = scrape_index(self._index_name)
            self.finished.emit(result)
        except Exception as e:
            self.failed.emit(f"{e}\n\n{traceback.format_exc()}")