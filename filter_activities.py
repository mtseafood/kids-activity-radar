#!/usr/bin/env python3
"""對 activities.json 做二次篩選。

用法：
    python filter_activities.py --city 台中市
    python filter_activities.py --free-only
    python filter_activities.py --max-price 500 --age 3
    python filter_activities.py --input activities.json --output filtered.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def matches(act: dict, args: argparse.Namespace) -> bool:
    if args.city:
        city = args.city.replace("臺", "台")
        if act.get("location_city") and city not in act["location_city"]:
            return False
        if act.get("location_city") is None and not args.keep_unknown:
            return False
    if args.free_only and not act.get("is_free"):
        return False
    if args.max_price is not None:
        price = act.get("price")
        if price is not None and price > args.max_price:
            return False
    if args.age is not None:
        if act.get("age_min") is not None and act["age_min"] > args.age:
            return False
        if act.get("age_max") is not None and act["age_max"] < args.age:
            return False
    if args.tag:
        if not any(args.tag in t for t in act.get("tags", [])):
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="二次篩選 activities.json")
    parser.add_argument("--input", default="activities.json")
    parser.add_argument("--output", default=None, help="輸出檔名（預設印到終端）")
    parser.add_argument("--city", help="只保留指定縣市")
    parser.add_argument("--free-only", action="store_true", help="只保留免費活動")
    parser.add_argument("--max-price", type=int, help="價格上限")
    parser.add_argument("--age", type=int, help="孩子年齡，保留涵蓋此年齡的活動")
    parser.add_argument("--tag", help="只保留包含此 tag 的活動，如：DIY手作")
    parser.add_argument(
        "--keep-unknown", action="store_true",
        help="縣市未知的活動也保留（預設用 --city 時會排除）",
    )
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        print(f"找不到 {path}，請先執行 scraper.py", file=sys.stderr)
        return 1

    data = json.loads(path.read_text(encoding="utf-8"))
    filtered = [a for a in data.get("activities", []) if matches(a, args)]
    result = {
        "scraped_at": data.get("scraped_at"),
        "total": len(filtered),
        "activities": filtered,
    }

    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"已寫入 {args.output}（{len(filtered)} 筆）")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
