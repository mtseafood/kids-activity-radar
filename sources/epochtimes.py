"""大紀元（台灣）親子活動頁 scraper — 靜態頁面，requests + BeautifulSoup。"""
from __future__ import annotations

import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import (
    Activity, BaseScraper, normalize_city,
    parse_age, parse_date_range, parse_price,
)

logger = logging.getLogger("scraper")

# 大紀元台灣站相關版面（副刊/文化/地方），靠關鍵字過濾親子活動報導
LIST_URLS = [
    "https://www.epochtimes.com.tw/b5/category/id/149",  # 副刊
    "https://www.epochtimes.com.tw/b5/category/id/150",  # 文化
    "https://www.epochtimes.com.tw/b5/category/id/151",  # 地方
]

RELEVANT_KEYWORDS = ["親子", "幼兒", "兒童", "DIY", "體驗", "小小"]


class EpochTimesScraper(BaseScraper):
    name = "epochtimes"

    def scrape(self) -> list[Activity]:
        activities: list[Activity] = []
        seen: set[str] = set()
        for list_url in LIST_URLS:
            resp = self.get(list_url)
            if resp is None:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.select("a[href]"):
                title = a.get_text(strip=True)
                href = a["href"]
                if not title or len(title) < 8:
                    continue
                if not any(k in title for k in RELEVANT_KEYWORDS):
                    continue
                url = urljoin(list_url, href)
                if url in seen:
                    continue
                seen.add(url)
                act = self._parse_article(url, title)
                if act:
                    activities.append(act)
        return activities

    def _parse_article(self, url: str, title: str) -> Activity | None:
        resp = self.get(url)
        if resp is None:
            return None
        try:
            soup = BeautifulSoup(resp.text, "html.parser")
            body = soup.select_one("article") or soup.select_one(".post-content") or soup
            text = body.get_text(" ", strip=True)[:3000]
            date_start, date_end = parse_date_range(text)
            age_min, age_max = parse_age(text)
            price, is_free = parse_price(text)
            return Activity(
                title=title,
                url=url,
                date_start=date_start,
                date_end=date_end,
                location_city=normalize_city(text),
                age_min=age_min,
                age_max=age_max,
                price=price,
                is_free=is_free,
                summary=text[:200],
                source=self.name,
            )
        except Exception as e:
            self.errors.append(f"[epochtimes] 解析 {url} 失敗: {e}")
            return None
