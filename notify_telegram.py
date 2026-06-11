#!/usr/bin/env python3
"""比對前後兩次爬取結果，把新增的活動推播到 Telegram。

用法：
    TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=yyy \
        python notify_telegram.py previous.json activities.json [site_url]

- 以活動 URL 當唯一鍵比對新增
- 台中市的新活動優先列出，其他縣市只報數量
- previous.json 不存在時（首次執行）只發上線通知
"""
from __future__ import annotations

import html
import json
import os
import sys
from pathlib import Path

import requests

MAX_ITEMS = 10


def load(path: str) -> dict | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return None


def send(token: str, chat_id: str, text: str) -> None:
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=20,
    )
    resp.raise_for_status()


def fmt_item(a: dict) -> str:
    date = a.get("date_start") or "日期見活動頁"
    free = "🆓" if a.get("is_free") else (f"${a['price']}" if a.get("price") is not None else "")
    title = html.escape(a.get("title", "")[:40])
    url = html.escape(a.get("url", ""), quote=True)
    return f"• <a href=\"{url}\">{title}</a>｜{date} {free}"


def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("缺少 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID，跳過推播")
        return 0

    prev_path = sys.argv[1] if len(sys.argv) > 1 else "previous.json"
    curr_path = sys.argv[2] if len(sys.argv) > 2 else "activities.json"
    site_url = sys.argv[3] if len(sys.argv) > 3 else ""

    curr = load(curr_path)
    if curr is None:
        print(f"讀不到 {curr_path}，跳過推播")
        return 0
    prev = load(prev_path)

    footer = f"\n\n📱 完整清單：{html.escape(site_url)}" if site_url else ""

    if prev is None:
        send(token, chat_id, (
            f"🎪 <b>親子活動雷達上線囉！</b>\n"
            f"目前共收錄 {curr.get('total', 0)} 個活動，每天早上自動更新。{footer}"
        ))
        return 0

    prev_urls = {a.get("url") for a in prev.get("activities", [])}
    new_acts = [a for a in curr.get("activities", []) if a.get("url") not in prev_urls]
    if not new_acts:
        print("沒有新活動，不推播")
        return 0

    taichung = [a for a in new_acts if a.get("location_city") == "台中市"]
    others = [a for a in new_acts if a.get("location_city") != "台中市"]

    lines = [f"🎪 <b>今日新發現 {len(new_acts)} 個親子活動</b>"]
    if taichung:
        lines.append(f"\n📍 <b>台中市（{len(taichung)} 個）</b>")
        lines += [fmt_item(a) for a in taichung[:MAX_ITEMS]]
        if len(taichung) > MAX_ITEMS:
            lines.append(f"…還有 {len(taichung) - MAX_ITEMS} 個")
    if others:
        lines.append(f"\n🗺 其他縣市新增 {len(others)} 個")
        lines += [fmt_item(a) for a in others[: max(0, MAX_ITEMS - len(taichung))]]

    send(token, chat_id, "\n".join(lines) + footer)
    print(f"已推播 {len(new_acts)} 個新活動")
    return 0


if __name__ == "__main__":
    sys.exit(main())
