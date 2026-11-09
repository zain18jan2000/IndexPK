"""
PSX index constituents scraper (bsl.com.pk).

Importable module + CLI.

Module use:
    from scraper.psx_index_scraper import scrape_index, scrape_indices, available_indices

    res = scrape_index("KMI-30")                    # -> ScrapeResult
    for row in res.rows:
        print(row["Ticker"], row["Weight"])

    both = scrape_indices(["KMI-30", "KSE-100"])    # one browser session
    scrape_index("KSE-100", save_csv=True, outdir="data/")

CLI use:
    python -m scraper.psx_index_scraper
    python -m scraper.psx_index_scraper KMI-30 KSE-100 --outdir data
    python -m scraper.psx_index_scraper KMI-30 --no-save --headed
"""
from __future__ import annotations

import argparse
import csv
import logging
import random
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from playwright.sync_api import Page, TimeoutError as PWTimeout, sync_playwright

log = logging.getLogger(__name__)

EXPECTED_HEADERS = ["Ticker", "Sector", "Price", "Today %", "Weight", "Mkt Cap", "Volume"]
MAX_RETRIES = 3
DEFAULT_TIMEOUT_MS = 60_000
DEFAULT_VIEWPORT = {"width": 1366, "height": 900}

# --- index registry -------------------------------------------------------
# Public canonical name -> URL. Add more indices here if the layout matches.
_INDICES: dict[str, str] = {
    "KMI-30":  "https://www.bsl.com.pk/indices/kmi-30/",
    "KSE-100": "https://www.bsl.com.pk/indices/kse-100/",
}

# Loose aliases (normalised: lowercase, alnum only) -> canonical name
_ALIASES = {
    "kmi30":  "KMI-30",
    "kse100": "KSE-100",
}


# --- public data type -----------------------------------------------------

@dataclass
class ScrapeResult:
    index: str
    rows: list[dict]
    as_of: str = ""
    expected_count: Optional[int] = None
    csv_path: Optional[Path] = None

    def __len__(self) -> int:
        return len(self.rows)

    def __iter__(self):
        return iter(self.rows)

    def __getitem__(self, i):
        return self.rows[i]

    def to_dicts(self) -> list[dict]:
        """Rows with the index name attached — handy for DataFrame construction."""
        return [{"Index": self.index, **r} for r in self.rows]


def available_indices() -> list[str]:
    """Canonical names accepted by scrape_index/scrape_indices."""
    return list(_INDICES)


def _normalize(name: str) -> str:
    s = name.strip()
    if s in _INDICES:
        return s
    key = re.sub(r"[^a-z0-9]", "", s.lower())
    if key in _ALIASES:
        return _ALIASES[key]
    raise ValueError(
        f"Unknown index {name!r}. Available: {', '.join(_INDICES)}"
    )


# --- page extraction (internal) -------------------------------------------

def _extract_table(page: Page, timeout_ms: int) -> list[dict]:
    table = page.locator("table").filter(has=page.locator("th", has_text="Weight")).first
    table.wait_for(state="attached", timeout=timeout_ms)

    headers = [h.strip() for h in table.locator("thead th").all_inner_texts()]
    missing = [h for h in EXPECTED_HEADERS if h not in headers]
    if missing:
        raise RuntimeError(
            f"Table layout changed. Missing columns: {missing}. Found: {headers}"
        )

    rows: list[dict] = []
    for tr in table.locator("tbody tr").all():
        cells = [c.strip() for c in tr.locator("td").all_inner_texts()]
        if len(cells) < len(headers):
            continue
        record = dict(zip(headers, cells))

        href = tr.locator("a[href*='/stocks/']").first.get_attribute("href") or ""
        m = re.search(r"/stocks/([^/]+)/?", href)
        ticker = m.group(1) if m else record["Ticker"].split()[0]
        lines = [l.strip() for l in record["Ticker"].splitlines() if l.strip()]
        lines = [l for l in lines if l != ticker and not l.endswith(" logo")]
        company = " ".join(lines) or record["Ticker"].replace(ticker, "", 1).strip()

        rows.append({
            "Ticker":   ticker,
            "Company":  company,
            "Sector":   record["Sector"],
            "Price":    record["Price"],
            "Today %":  record["Today %"],
            "Weight":   record["Weight"],
            "Mkt Cap":  record["Mkt Cap"],
            "Volume":   record["Volume"],
        })
    return rows


def _extract_as_of(page: Page) -> str:
    try:
        text = page.get_by_text(re.compile(r"As of")).first.inner_text(timeout=5_000)
        m = re.search(r"As of[^·]*·\s*(.+)", text)
        return m.group(1).strip() if m else text.strip()
    except Exception:
        return ""


def _extract_expected_count(page: Page) -> Optional[int]:
    try:
        text = page.get_by_text(re.compile(r"^\s*\d+\s+names\s*$")).first.inner_text(timeout=5_000)
        return int(re.search(r"\d+", text).group())
    except Exception:
        return None


def _scrape_one(
    page: Page,
    name: str,
    timeout_ms: int,
    debug_screenshots: bool,
) -> tuple[list[dict], str, Optional[int]]:
    url = _INDICES[name]
    last_err: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log.info("[%s] attempt %d/%d: %s", name, attempt, MAX_RETRIES, url)
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            rows = _extract_table(page, timeout_ms)
            if not rows:
                raise RuntimeError("Constituents table found but empty.")
            return rows, _extract_as_of(page), _extract_expected_count(page)
        except (PWTimeout, RuntimeError) as e:
            last_err = e
            log.warning("  %s failed: %s", name, e)
            if debug_screenshots:
                slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
                try:
                    page.screenshot(path=f"{slug}_error_attempt{attempt}.png", full_page=True)
                except Exception:
                    pass
            time.sleep(5 * attempt)

    raise RuntimeError(f"[{name}] gave up after {MAX_RETRIES} attempts: {last_err}")


def _save_csv(name: str, rows: list[dict], as_of: str, outdir: Path) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out = outdir / f"{slug}_constituents_{stamp}.csv"
    scraped_at = datetime.now().isoformat(timespec="seconds")
    fields = ["Index"] + list(rows[0].keys()) + ["As Of", "Scraped At"]

    with out.open("w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig => Excel-friendly
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({"Index": name, **r, "As Of": as_of, "Scraped At": scraped_at})
    return out


# --- public API -----------------------------------------------------------

def scrape_indices(
    indices: Iterable[str] = (),
    *,
    save_csv: bool = False,
    outdir: str | Path = ".",
    headless: bool = True,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    strict: bool = True,
    debug_screenshots: bool = False,
) -> dict[str, ScrapeResult]:
    """
    Scrape one or more indices. Returns {canonical_name: ScrapeResult}.

    Empty `indices` -> all registered indices.

    strict=True  : raise on the first index that fails.
    strict=False : log the failure and continue with the remaining indices.

    The browser is launched once and reused for every index in the call, so
    prefer passing a list to a loop of single `scrape_index(...)` calls.
    """
    names: list[str] = []
    for raw in (list(indices) or _INDICES.keys()):
        n = _normalize(raw)
        if n not in names:
            names.append(n)

    outdir_p = Path(outdir).resolve()
    if save_csv:
        outdir_p.mkdir(parents=True, exist_ok=True)

    results: dict[str, ScrapeResult] = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        context = browser.new_context(viewport=DEFAULT_VIEWPORT, locale="en-US")
        page = context.new_page()
        try:
            for i, name in enumerate(names):
                if i:
                    time.sleep(random.uniform(2, 4))  # polite pause between pages
                try:
                    rows, as_of, expected = _scrape_one(
                        page, name, timeout_ms, debug_screenshots
                    )
                except Exception as e:
                    if strict:
                        raise
                    log.error("  %s: %s", name, e)
                    continue

                if expected is not None and len(rows) != expected:
                    log.warning(
                        "  %s: page says %d names, scraped %d",
                        name, expected, len(rows),
                    )

                csv_path = _save_csv(name, rows, as_of, outdir_p) if save_csv else None
                if csv_path:
                    log.info("  %s: saved %d rows -> %s", name, len(rows), csv_path.name)

                results[name] = ScrapeResult(name, rows, as_of, expected, csv_path)
        finally:
            context.close()
            browser.close()

    return results


def scrape_index(index: str, **kwargs) -> ScrapeResult:
    """Scrape a single index by name (e.g. 'KMI-30', 'kse-100', 'KSE100')."""
    name = _normalize(index)
    return scrape_indices([name], **kwargs)[name]


def scrape_all(**kwargs) -> dict[str, ScrapeResult]:
    """Scrape every registered index in one browser session."""
    return scrape_indices([], **kwargs)


# --- CLI ------------------------------------------------------------------

def _cli(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    p = argparse.ArgumentParser(
        prog="psx_index_scraper",
        description="Scrape PSX index constituents from bsl.com.pk",
    )
    p.add_argument(
        "indices", nargs="*",
        help=f"Any of: {', '.join(_INDICES)}. Default: all.",
    )
    p.add_argument("--outdir", default=".", help="Folder for CSVs (default: current).")
    p.add_argument("--save", action=argparse.BooleanOptionalAction, default=True,
                   help="Write CSV files (default: on).")
    p.add_argument("--headed", action="store_true", help="Show the browser window.")
    p.add_argument("--debug-screenshots", action="store_true",
                   help="Save a PNG when a page fails.")
    args = p.parse_args(argv)

    try:
        results = scrape_indices(
            args.indices or [],
            save_csv=args.save,
            outdir=args.outdir,
            headless=not args.headed,
            strict=False,
            debug_screenshots=args.debug_screenshots,
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if not results:
        print("Nothing scraped.", file=sys.stderr)
        return 1

    for name, res in results.items():
        suffix = f" -> {res.csv_path.name}" if res.csv_path else ""
        print(f"{name}: {len(res.rows)} rows (as of: {res.as_of or 'unknown'}){suffix}")

    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())