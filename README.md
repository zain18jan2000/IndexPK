# IndexPK

A desktop guide that helps non-technical investors decide **how to split a lump sum across the constituent companies of a PSX index** (KMI-30 or KSE-100), based on the latest published index weights from [bsl.com.pk](https://www.bsl.com.pk).

It is **not** a trading app, not a broker, and not financial advice. It fetches current weights, lets you pick how diversified you want to be, and shows you a clean PKR-by-company allocation table.

---

## Table of contents

- [What it does](#what-it-does)
- [Screens & flow](#screens--flow)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Running the app](#running-the-app)
- [Project structure](#project-structure)
- [How the allocation is computed](#how-the-allocation-is-computed)
- [Current status](#current-status)
- [Roadmap](#roadmap)
- [Disclaimer](#disclaimer)

---

## What it does

You tell IndexPK three things:

1. **Which index** you want to follow — KMI-30 (30 largest Shariah-compliant companies) or KSE-100 (Pakistan's headline benchmark).
2. **How much money** you want to invest, in PKR.
3. **How many companies** you want to spread it across (with sensible minimums and maximums per index).

It then scrapes the live "Top constituents" table from bsl.com.pk, reads the index weight for every company, and produces a **diversified allocation plan**:

- the **% of your money** to put into each company
- the **exact PKR amount** per company
- a **summary total** that matches what you typed (down to the paisa)

The result is a plain-English buy list you can take to any broker.

---

## Screens & flow

The app is a 4-step wizard with locked tabs that unlock as you progress.

| Step | Tab | What you do |
|------|-----|-------------|
| 1 | **Pick an Index** | Choose KMI-30 or KSE-100. Read the disclaimer. |
| 2 | **Investment Amount** | Enter the amount you want to invest (PKR). |
| 3 | **Customize Portfolio** | Watch the live constituent table load from bsl.com.pk. Drag the slider to pick how many companies to diversify across. |
| 4 | **Your Portfolio** | See the final allocation: ticker, company, index weight, allocation %, and PKR amount per company. |

Tabs 2–4 remain disabled until the previous step is completed. Tabs 1–2 are locked while a scrape is in flight so you can't invalidate a running fetch.

---

## Features

- **Live data** — scrapes the official bsl.com.pk constituents tables for KMI-30 and KSE-100, no bundled snapshots.
- **Background scraping** — Playwright runs in a `QThread` worker so the UI never freezes during the 10–20 second fetch.
- **Diversification slider** — pick between **7** and **25** companies for KMI-30, or **7** and **75** for KSE-100. Defaults are **15** and **25** respectively.
- **Weight-normalised allocation** — the selected companies' index weights are re-scaled to 100%, then applied to your amount (so your money stays fully invested, even if the top-N companies only account for, say, 90% of the index by weight).
- **Exact totals** — per-company PKR amounts are rounded to 2 decimals, and the largest position absorbs any residual paisa, so the sum always equals the amount you entered.
- **Cached per index** — changing the amount or slider re-uses the last scrape; only switching indices triggers a new fetch.
- **Graceful failures** — network errors surface a friendly "Could not fetch data" page with a **Try Again** button and full details in the log.
- **Polished UI** — custom Qt stylesheet, IBM-inspired green palette, drop-shadow cards, styled tables and sliders.

---

## Requirements

- **Python 3.11+** (uses `str | None` type syntax).
- **PySide6** — the Qt binding powering the GUI.
- **Playwright** — drives a headless browser to scrape bsl.com.pk.
- **platformdirs** — cross-platform paths for user data and logs.

Tested on **Linux** and **Windows**. macOS should work but has not been verified end-to-end.

---

## Installation

```bash
# 1. clone / enter the project
cd Investo

# 2. create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows

# 3. install Python dependencies
pip install -r requirements.txt

# 4. install the Playwright browser once
playwright install chromium
```

---

## Running the app

```bash
python main.py
```

That's it. The window opens on **Tab 1 — Pick an Index**.

### What you should see on launch

- White/off-white background, green accent colour.
- Logo in the top-left (from `assets/logo.png`).
- A single card with two buttons: **Invest in KMI-30** and **Invest in KSE-100**.
- A short disclaimer card below the buttons.
- Tabs 2–4 greyed out until you make a choice.

### Suggested first run

1. Click **Invest in KMI-30** → you land on Tab 2.
2. Leave the default `100,000` or enter your own amount → click **Calculate My Allocation**.
3. Wait ~10–20 s while the constituents table loads.
4. Adjust the slider (default **15** companies, range **7–25**) → click **Build My Portfolio**.
5. Review the allocation on Tab 4. The **Total to invest** at the bottom will match the amount you typed exactly.

To try KSE-100, go back to Tab 1, pick the other index, and the app will re-scrape with KSE-100 defaults (slider at **25**, max **75**).

---

## Project structure

```
Investo/
├── main.py                        # launcher — QApplication, MainWindow, SIGINT handling
├── requirements.txt
├── setup.sh
├── README.md
├── assets/
│   └── logo.png                   # 499×199, displayed at 180 px wide
├── app/
│   ├── __init__.py
│   ├── paths.py                   # ASSETS_DIR (bundled), DATA_DIR / LOG_DIR (per-user)
│   ├── main_window.py             # all 4 tabs + MainWindow + allocation math
│   ├── table_model.py             # ConstituentsModel, PortfolioModel, weight_value
│   ├── table_style.py             # shared QSS for tables + scrollbars
│   └── worker.py                  # ScrapeWorker (QThread background bridge)
└── scraper/
    ├── __init__.py
    └── psx_index_scraper.py       # Playwright scraper — importable + CLI
```

### Notable design choices

- **`app/paths.py`** resolves paths correctly in both dev and PyInstaller-frozen builds, so the same code works before and after packaging.
- **`scraper/psx_index_scraper.py`** is completely UI-agnostic — it exposes `scrape_index("KMI-30")` returning a `ScrapeResult` dataclass. You can use it from Python, from the CLI, or from the app without changes.
- **`app/worker.py`** wraps the sync Playwright call so it runs on a background thread; the UI thread stays responsive.
- **`app/table_style.py`** keeps every visual tweak out of the window code, so the widgets stay focused on layout.

---

## How the allocation is computed

Suppose you choose **KMI-30**, **PKR 100,000**, and **15 companies**.

**Step 1 — pick the top 15 by index weight.**

The scraped rows are sorted by weight descending. The top 15 companies sum to, for example, **90.18%** of the full index.

**Step 2 — re-normalise to 100%.**

Since you're only investing in these 15, their weights are re-scaled so they account for your full amount:

```
FFC allocation % = (12.09 / 90.18) × 100 = 13.41%
```

**Step 3 — convert to PKR.**

```
FFC amount = (13.41 / 100) × 100,000 = PKR 13,406.52
```

**Step 4 — correct rounding.**

The naive sum of rounded PKR amounts can drift by a few paisa. IndexPK adds that residual to the largest position so the **Total to invest** shown at the bottom of Tab 4 is exactly what you typed.

You can inspect the implementation in `app/main_window.py` → `_compute_allocations()`.

---

## Current status

| Area | Status |
|------|--------|
| Tab 1 — Pick an Index | ✅ complete |
| Tab 2 — Investment Amount | ✅ complete |
| Tab 3 — Customize Portfolio (live scrape + slider) | ✅ complete |
| Tab 4 — Your Portfolio (allocation table + total) | ✅ complete |
| Background scraping worker | ✅ complete |
| Cached per index (no re-scrape on amount / slider change) | ✅ complete |
| Error page + retry | ✅ complete |
| Qt styling (tabs, cards, tables, slider) | ✅ complete |
| Logging to file | ⏳ planned |
| CSV / Excel export of the portfolio | ⏳ planned |
| Packaged installers (Briefcase / PyInstaller) | ⏳ planned |

The app is fully functional as a local desktop tool today; the roadmap below covers the remaining polish and distribution work.

---

## Roadmap

- [ ] **Logging to file** — write to `platformdirs.user_log_dir("IndexPK")` so non-technical users can attach a log when reporting issues.
- [ ] **Diagnostics export** — one-click zip of the log, Python version, and scraper version.
- [ ] **Export portfolio to CSV / Excel** — from Tab 4.
- [ ] **Sector breakdown** — group the allocated companies by sector in a secondary view.
- [ ] **Persistent settings** — remember last index, amount, and slider value between launches.
- [ ] **Update check** — banner when a newer release is available on GitHub.
- [ ] **Packaging** — Briefcase for `.msi` / `.dmg` / `.AppImage` with code-signing.
- [ ] **First-run disclaimer confirmation** — one-time dialog before the first calculation.

---

## Disclaimer

IndexPK is a **guide**, not an advisor.

- It is intended for **long-term, buy-and-hold** investors.
- It suggests how to divide a lump sum based on **published index weights**, which change over time.
- **This is not financial advice.** Returns are never guaranteed — markets can fall as well as rise.
- You alone are responsible for your own investment decisions.

If you need personalised advice, consult a licensed financial advisor.

---

## License

Not yet decided. Treat the source as reference-only until a license is added.