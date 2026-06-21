"""文化部「全國藝文活動資訊」open data scraper（涵蓋全台各縣市）。

端點 https://cloud.culture.tw/frontsite/trans/SearchShowAction.do
以 category 分類一次回傳該類全部活動 JSON。本來源不限單一縣市，
直接從活動地點字串判斷縣市，交由 filter_and_rank 依目標縣市篩選——
這讓我們用「單一全國來源」就能涵蓋台中／苗栗／彰化／南投等中部各縣市。
"""
from __future__ import annotations

import json
import logging
import re

from .base import Activity, BaseScraper, parse_age, parse_price

logger = logging.getLogger("scraper")

API = "https://cloud.culture.tw/frontsite/trans/SearchShowAction.do?method=doFindTypeJ&category={cat}"
DETAIL = "https://cloud.culture.tw/frontsite/inquiry/eventInquiryAction.do?method=showEventDetail&uid={uid}"

# 涵蓋的活動分類（涵蓋親子、展覽、戲劇、綜藝等可能含親子場次的類別）
CATEGORIES = [1, 2, 3, 4, 5, 6, 7, 11]

RELEVANT_KEYWORDS = [
    "親子", "幼兒", "兒童", "DIY", "手作", "體驗", "小小",
    "工作坊", "繪本", "故事", "感統", "童", "寶寶",
]

CITY_RE = re.compile(r"([一-鿿]{2}[市縣])")


def _detect_city(location: str) -> str | None:
    """從地點字串抓出縣市名（臺→台）。"""
    if not location:
        return None
    m = CITY_RE.search(location.replace("臺", "台"))
    return m.group(1) if m else None


def _to_iso(d: str) -> str | None:
    """2026/06/23 → 2026-06-23。"""
    if not d:
        return None
    m = re.match(r"(\d{4})/(\d{1,2})/(\d{1,2})", d.strip())
    if not m:
        return None
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


class CultureCloudScraper(BaseScraper):
    name = "culture_cloud"

    def scrape(self) -> list[Activity]:
        seen_uid: set[str] = set()
        activities: list[Activity] = []
        for cat in CATEGORIES:
            resp = self.get(API.format(cat=cat))
            if resp is None:
                continue
            try:
                rows = resp.json()
            except ValueError as e:
                self.errors.append(f"[{self.name}] cat={cat} JSON 解析失敗: {e}")
                continue
            for row in rows:
                uid = row.get("UID")
                if uid and uid in seen_uid:
                    continue
                if uid:
                    seen_uid.add(uid)
                try:
                    act = self._from_row(row)
                    if act:
                        activities.append(act)
                except Exception as e:  # noqa: BLE001
                    self.errors.append(f"[{self.name}] 單筆解析失敗: {e}")
            self.sleep()
        return activities

    def _from_row(self, row: dict) -> Activity | None:
        title = (row.get("title") or "").strip()
        if not title:
            return None

        shows = row.get("showInfo") or []
        first = shows[0] if shows else {}
        location = (first.get("location") or "").strip()
        loc_name = (first.get("locationName") or "").strip()

        # 親子相關才留（標題或場館名命中關鍵字）
        haystack = title + " " + loc_name + " " + (row.get("descriptionFilterHtml") or "")
        if not any(k in haystack for k in RELEVANT_KEYWORDS):
            return None

        city = _detect_city(location) or _detect_city(loc_name)
        # 地址去掉開頭的縣市與郵遞區號，保留可讀地址
        address = location or None

        date_start = _to_iso(row.get("startDate") or "")
        date_end = _to_iso(row.get("endDate") or "")

        price_text = str(first.get("price") or "")
        on_sales = (first.get("onSales") or "").upper() == "Y"
        price, is_free = parse_price(price_text)
        if price is None:
            is_free = not on_sales
            price = None if on_sales else 0

        age_min, age_max = parse_age(title)

        url = (row.get("sourceWebPromote") or "").strip()
        if not url.startswith("http"):
            url = DETAIL.format(uid=row.get("UID", ""))

        organizer = (row.get("showUnit") or row.get("masterUnit") or "").strip() or None
        if isinstance(organizer, list):
            organizer = "、".join(organizer) or None

        return Activity(
            title=title,
            url=url,
            date_start=date_start,
            date_end=date_end,
            location_city=city,
            location_address=address,
            age_min=age_min,
            age_max=age_max,
            price=price,
            is_free=is_free,
            summary=f"{title}｜{loc_name or address or ''}",
            organizer=organizer,
            source=self.name,
        )
