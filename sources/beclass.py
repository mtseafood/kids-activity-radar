"""BeClass 線上報名系統 scraper（民間活動報名平台）。

BeClass 是台灣老牌報名平台，許多小型工作室、協會的親子活動在此報名。
站內搜尋需要先 GET 搜尋頁取得 CSRF token 與 session cookie，
再 POST /default.php?name=Search&op=regist。

搜尋結果連結格式：https://www.beclass.com/rid=<id>，
標題尾端常帶活動日期「(2026-04-19)」。
"""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from .base import Activity, BaseScraper, parse_age, parse_date, parse_price

logger = logging.getLogger("scraper")

SEARCH_PAGE = "https://www.beclass.com/default.php?name=Search"
SEARCH_POST = "https://www.beclass.com/default.php?name=Search&op=regist"

CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')
# 結果列表的標題尾端註記：(2026-04-19)、(截止報名。)、(報名期限N天) 等
NOTE_RE = re.compile(r"\((截止報名。?|報名期限[^)]*|\d{4}-\d{2}-\d{2})\)")


class BeClassScraper(BaseScraper):
    name = "beclass"

    def __init__(self, city: str = "台中市", days: int = 60):
        super().__init__(city=city, days=days)
        prefix = city[:2]  # 台中市 → 台中
        self.keywords = [
            f"{prefix} 親子", f"{prefix} 兒童", f"{prefix} DIY",
            f"{prefix} 手作", f"{prefix} 幼兒",
        ]

    def scrape(self) -> list[Activity]:
        token = self._fetch_csrf()
        if token is None:
            return []
        activities: list[Activity] = []
        seen: set[str] = set()
        for kw in self.keywords:
            html = self._search(kw, token)
            if html is None:
                continue
            for act in self._parse_results(html):
                if act.url not in seen:
                    seen.add(act.url)
                    activities.append(act)
        return activities

    def _fetch_csrf(self) -> str | None:
        resp = self.get(SEARCH_PAGE)
        if resp is None:
            return None
        m = CSRF_RE.search(resp.text)
        if not m:
            self.errors.append(f"[{self.name}] 找不到 CSRF token，搜尋頁可能改版")
            return None
        return m.group(1)

    def _search(self, keyword: str, token: str) -> str | None:
        try:
            resp = self.session.post(
                SEARCH_POST,
                data={"search_query": keyword, "csrf_token": token},
                timeout=20,
            )
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            self.errors.append(f"[{self.name}] 搜尋 {keyword} 失敗: {e}")
            return None
        finally:
            self.sleep()

    def _parse_results(self, html: str) -> list[Activity]:
        soup = BeautifulSoup(html, "html.parser")
        out: list[Activity] = []
        for a in soup.select("a[href*='rid=']"):
            try:
                act = self._from_link(a)
                if act:
                    out.append(act)
            except Exception as e:
                self.errors.append(f"[{self.name}] 單筆解析失敗: {e}")
        return out

    def _from_link(self, a) -> Activity | None:
        url = a["href"]
        if url.startswith("/"):
            url = "https://www.beclass.com" + url
        raw = a.get_text(" ", strip=True)
        if not raw:
            return None
        # 已截止的活動直接略過
        if "截止報名" in raw:
            return None
        title = NOTE_RE.sub("", raw).strip()
        # 標題沒提到目標城市的略過（搜尋可能命中內文）
        if self.city[:2] not in title.replace("臺", "台"):
            return None

        date_start = parse_date(raw)
        age_min, age_max = parse_age(title)
        price, is_free = parse_price(title)
        return Activity(
            title=title,
            url=url,
            date_start=date_start,
            date_end=date_start,
            location_city=self.city,
            age_min=age_min,
            age_max=age_max,
            price=price,
            is_free=is_free,
            summary=title,
            source=self.name,
        )
