"""Accupass 活動通 scraper。

Accupass 搜尋頁是伺服器端渲染，活動卡片直接存在於 HTML 中，
用 requests + BeautifulSoup 解析即可；若改版成純前端渲染
（抓不到卡片）則 fallback 到 Playwright。

卡片文字格式（以 | 分隔）：
    2026.09.19 (Sat) 15:00 - 16:00 | 活動標題 | Taoyuan City | # | 標籤 | ...
"""
from __future__ import annotations

import logging
from urllib.parse import quote

from bs4 import BeautifulSoup

from .base import (
    Activity, BaseScraper, normalize_city,
    parse_age, parse_date_range,
)

logger = logging.getLogger("scraper")

SEARCH_KEYWORDS = ["小小", "幼兒", "親子", "體驗", "DIY"]
# 各縣市再加上「縣市名 + 主題」的在地化查詢，補足非台中縣市的活動
CITY_TOPICS = ["親子", "體驗", "DIY", "小小"]
SEARCH_URL = "https://www.accupass.com/search?q={kw}"

# 親子正向關鍵字：加上縣市查詢後結果較雜（會混進聯誼/說明會/場地出租），
# 標題或內文需命中以下其一才視為親子活動。
KID_KEYWORDS = [
    "親子", "兒童", "幼兒", "寶寶", "小小", "繪本", "故事", "感統",
    "DIY", "手作", "夏令營", "冬令營", "營隊", "體驗營", "童",
    "彩繪", "黏土", "陶藝", "烘焙", "烹飪", "科學", "積木", "扮演",
]


class AccupassScraper(BaseScraper):
    name = "accupass"

    def _keywords(self) -> list[str]:
        kws = list(SEARCH_KEYWORDS)
        for c in self.cities:
            prefix = c[:2]  # 台中市 → 台中
            for topic in CITY_TOPICS:
                kws.append(f"{prefix} {topic}")
        # 去重並保留順序
        seen, out = set(), []
        for k in kws:
            if k not in seen:
                seen.add(k)
                out.append(k)
        return out

    def scrape(self) -> list[Activity]:
        activities: list[Activity] = []
        seen: set[str] = set()
        for kw in self._keywords():
            url = SEARCH_URL.format(kw=quote(kw))
            resp = self.get(url)
            html = resp.text if resp else None
            if html is None or "/event/" not in html:
                logger.warning("[accupass] 靜態頁無卡片，改用 Playwright：%s", kw)
                html = self._render_playwright(url)
            if not html:
                continue
            for act in self._parse_cards(html):
                if act.url not in seen:
                    seen.add(act.url)
                    activities.append(act)
        return activities

    def _parse_cards(self, html: str) -> list[Activity]:
        soup = BeautifulSoup(html, "html.parser")
        out: list[Activity] = []
        seen: set[str] = set()
        for a in soup.select("a[href^='/event/']"):
            href = a["href"].split("?")[0]
            if href in seen:
                continue
            seen.add(href)
            try:
                # 往上找整張卡片的容器（含日期/城市/價格）
                card = a.find_parent(
                    "div", class_=lambda c: c and "card-wrapper" in c
                )
                parts = (card or a).get_text("|", strip=True).split("|")
                if len(parts) < 2:
                    continue
                date_text, title = parts[0], parts[1]
                rest = " ".join(parts[2:])
                # 親子相關才留（過濾掉聯誼/說明會/場地出租等雜訊）
                if not any(k in (title + rest) for k in KID_KEYWORDS):
                    continue
                date_start, date_end = parse_date_range(date_text)
                age_min, age_max = parse_age(title + " " + rest)
                # 卡片尾端的數字是瀏覽/收藏數，不是價格——
                # 列表頁抓不到可靠價格，只判斷「免費」字樣
                is_free = True if "免費" in (title + rest) else None
                price = 0 if is_free else None
                out.append(Activity(
                    title=title,
                    url="https://www.accupass.com" + href,
                    date_start=date_start,
                    date_end=date_end or date_start,
                    location_city=normalize_city(rest) or normalize_city(title),
                    age_min=age_min,
                    age_max=age_max,
                    price=price,
                    is_free=is_free,
                    summary=title,
                    source=self.name,
                ))
            except Exception as e:
                self.errors.append(f"[accupass] 卡片解析失敗 {href}: {e}")
        return out

    def _render_playwright(self, url: str) -> str | None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.errors.append("[accupass] Playwright 未安裝，跳過 fallback")
            return None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, timeout=30000, wait_until="networkidle")
                html = page.content()
                browser.close()
                return html
        except Exception as e:
            self.errors.append(f"[accupass] Playwright 渲染失敗 {url}: {e}")
            return None
