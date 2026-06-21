#!/usr/bin/env python3
"""檢查 activities.json 內各活動報名連結是否仍有效（失效偵測）。

用法：
    python check_links.py                      # 檢查並印出失效清單
    python check_links.py --output activities.json   # 把結果寫回（每筆加 link_ok 欄位）

只做唯讀檢查並回報；加 --output 時才會回寫 link_ok 標記，方便前端標示「可能已結束」。
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

UA = "Mozilla/5.0 (kids-activity-radar link checker)"
TIMEOUT = 12


def check(url: str) -> tuple[str, bool, str]:
    """回傳 (url, ok, note)。先試 HEAD，失敗或不支援再試 GET。"""
    if not url:
        return url, True, "無網址（略過）"
    for method in ("HEAD", "GET"):
        try:
            req = Request(url, method=method, headers={"User-Agent": UA})
            with urlopen(req, timeout=TIMEOUT) as resp:
                return url, 200 <= resp.status < 400, f"HTTP {resp.status}"
        except HTTPError as e:
            # 405：不支援 HEAD，換 GET 再試
            if e.code == 405 and method == "HEAD":
                continue
            return url, False, f"HTTP {e.code}"
        except (URLError, TimeoutError) as e:
            if method == "HEAD":
                continue
            return url, False, f"{type(e).__name__}: {str(e)[:40]}"
        except Exception as e:  # noqa: BLE001
            return url, False, f"{type(e).__name__}"
    return url, False, "連線失敗"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="activities.json")
    ap.add_argument("--output", help="把 link_ok 標記寫回此檔（預設只回報不寫入）")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    data = json.load(open(args.input, encoding="utf-8"))
    acts = data.get("activities", [])
    urls = [a.get("url", "") for a in acts]

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(check, urls))

    status = {u: (ok, note) for u, ok, note in results}
    dead = [(a["title"], a.get("url", ""), status[a.get("url", "")][1])
            for a in acts if not status[a.get("url", "")][0]]

    print(f"檢查 {len(acts)} 個連結：{len(acts) - len(dead)} 正常、{len(dead)} 失效")
    for title, url, note in dead:
        print(f"  ✗ [{note}] {title}\n      {url}")

    if args.output:
        for a in acts:
            a["link_ok"] = status[a.get("url", "")][0]
        json.dump(data, open(args.output, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print(f"\n已寫回 {args.output}（每筆新增 link_ok 欄位）")

    return 1 if dead else 0


if __name__ == "__main__":
    sys.exit(main())
