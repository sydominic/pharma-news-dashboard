from __future__ import annotations

import importlib.util
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

_REQUIRED_PACKAGES = {
    "pandas": "pandas",
    "feedparser": "feedparser",
    "requests": "requests",
    "bs4": "beautifulsoup4",
    "openpyxl": "openpyxl",
    "dateutil": "python-dateutil",
}
_missing = [pip_name for import_name, pip_name in _REQUIRED_PACKAGES.items() if importlib.util.find_spec(import_name) is None]
if _missing:
    subprocess.check_call([sys.executable, "-m", "pip", "install", *_missing])

from modules.news_cleaner import load_news, merge_existing, normalize_and_classify, save_news
from modules.rss_collector import collect_google_news

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CONFIG_PATH = DATA_DIR / "rss_sources.json"
RAW_PATH = DATA_DIR / "news_raw.csv"
CLEAN_PATH = DATA_DIR / "news_clean.csv"


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today()
    start = today - timedelta(days=6)
    print("[1/4] Collect Google News RSS")
    print(f"      Date scope: {start} ~ {today}")
    raw = collect_google_news(CONFIG_PATH, start_date=start, end_date=today)
    errors = raw.attrs.get("errors", []) if hasattr(raw, "attrs") else []
    raw.to_csv(RAW_PATH, index=False, encoding="utf-8-sig")
    print(f"      Raw rows: {len(raw)}")

    print("[2/4] Normalize and classify")
    clean = normalize_and_classify(raw)
    print(f"      Clean rows: {len(clean)}")

    print("[3/4] Merge existing")
    existing = load_news(CLEAN_PATH)
    merged = merge_existing(existing, clean)
    print(f"      Existing: {len(existing)} / Merged: {len(merged)}")

    print("[4/4] Save with retention policy")
    save_news(merged, CLEAN_PATH)
    print(f"Saved: {CLEAN_PATH}")
    print(f"Stats: {DATA_DIR / 'category_monthly_stats.csv'}")
    print(f"Stats: {DATA_DIR / 'keyword_weekly_stats.csv'}")
    print(f"Stats: {DATA_DIR / 'retention_summary.csv'}")
    if errors:
        print("\n[WARN] Some queries failed:")
        for err in errors:
            print(" -", err)


if __name__ == "__main__":
    main()
