#!/usr/bin/env python3
"""台灣親子體驗活動爬蟲（2~4 歲幼兒適用）。

用法：
    python scraper.py                     # 預設台中市、未來 60 天
    python scraper.py --city 台北市 --days 30
    python scraper.py --sources accupass kkday
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from sources import ALL_SCRAPERS
from filters import filter_and_rank

LOG_FILE = "scraper_errors.log"


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
        ],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="台灣親子體驗活動爬蟲")
    parser.add_argument("--city", default="台中市", help="優先縣市（預設：台中市）")
    parser.add_argument(
        "--cities", nargs="*", default=None,
        help="目標縣市清單（可多個，如：台中市 苗栗縣 彰化縣 南投縣）。未指定時使用 --city。",
    )
    parser.add_argument("--days", type=int, default=60, help="往後抓幾天內的活動（預設：60）")
    parser.add_argument("--output", default="activities.json", help="輸出檔名")
    parser.add_argument(
        "--sources", nargs="*", default=None,
        help="只跑指定來源（brands / niceday / pinkoi / beclass / accupass / kkday / "
             "epochtimes / taichung_culture / culture_cloud）",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    def _norm(c: str) -> str:
        c = c.replace("臺", "台")
        if not c.endswith(("市", "縣")):
            c += "市"
        return c

    # 縣市寫法正規化（臺中市 → 台中市；台中 → 台中市）
    city = _norm(args.city)
    cities = [_norm(c) for c in args.cities] if args.cities else [city]

    setup_logging(args.verbose)
    log = logging.getLogger("scraper")

    all_activities = []
    all_errors = []
    for scraper_cls in ALL_SCRAPERS:
        if args.sources and scraper_cls.name not in args.sources:
            continue
        log.info("=== 開始爬取：%s ===", scraper_cls.name)
        scraper = scraper_cls(city=city, days=args.days, cities=cities)
        try:
            items = scraper.scrape()
            log.info("[%s] 取得 %d 筆原始活動", scraper_cls.name, len(items))
            all_activities.extend(items)
        except Exception as e:
            # 單一來源整體失敗也不中斷其他來源
            log.error("[%s] 來源層級失敗: %s", scraper_cls.name, e, exc_info=True)
            all_errors.append(f"[{scraper_cls.name}] {e}")
        all_errors.extend(scraper.errors)

    filtered = filter_and_rank(all_activities, city=city, days=args.days, cities=cities)
    log.info("目標縣市 %s：篩選後保留 %d / %d 筆", "、".join(cities), len(filtered), len(all_activities))

    result = {
        "scraped_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(filtered),
        "activities": [a.to_dict() for a in filtered],
    }
    out_path = Path(args.output)
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info("已寫入 %s（錯誤 %d 筆，詳見 %s）", out_path, len(all_errors), LOG_FILE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
