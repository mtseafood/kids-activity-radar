"""台中市政府文化局藝文活動 scraper。

文化局活動查詢站（https://activity.culture.taichung.gov.tw/）提供
開放資料介接服務 `/_DataAction`，一次回傳全部活動 JSON，
比解析 HTML 穩定。注意：該端點回傳的 JSON 含尾逗號與控制字元，
需要先清理才能解析。
"""
from __future__ import annotations

import json
import logging
import re

from .base import (
    Activity, BaseScraper,
    parse_age, parse_date_range, parse_price,
)

logger = logging.getLogger("scraper")

DATA_URL = "https://activity.culture.taichung.gov.tw/_DataAction"
SITE_URL = "https://activity.culture.taichung.gov.tw/"

RELEVANT_KEYWORDS = [
    "親子", "幼兒", "兒童", "DIY", "手作", "體驗", "小小",
    "工作坊", "繪本", "故事", "感統",
]


class TaichungCultureScraper(BaseScraper):
    name = "taichung_culture"

    def scrape(self) -> list[Activity]:
        resp = self.get(DATA_URL)
        if resp is None:
            return []

        # 官方 JSON 不合法：物件結尾有尾逗號、字串含未跳脫的控制字元
        text = re.sub(r",\s*([}\]])", r"\1", resp.text)
        try:
            rows = json.loads(text, strict=False)["GenericData"]["Dataset"]["ROW"]
        except (ValueError, KeyError) as e:
            self.errors.append(f"[{self.name}] 開放資料 JSON 解析失敗: {e}")
            return []

        activities = []
        for row in rows:
            try:
                act = self._from_row(row)
                if act:
                    activities.append(act)
            except Exception as e:
                self.errors.append(f"[{self.name}] 單筆解析失敗: {e}")
        return activities

    def _from_row(self, row: dict) -> Activity | None:
        title = (row.get("活動名稱") or "").strip()
        if not title:
            return None
        # 只留親子相關活動
        haystack = title + " " + (row.get("地點") or "")
        if not any(k in haystack for k in RELEVANT_KEYWORDS):
            return None

        date_text = row.get("活動展演(起訖)") or ""
        date_start, date_end = parse_date_range(date_text)

        ticketed = (row.get("活動售票與否") or "").strip() == "是"
        price, is_free = parse_price(row.get("票價") or "")
        if price is None:
            is_free = not ticketed
            price = None if ticketed else 0

        age_min, age_max = parse_age(title)
        address = (row.get("地點") or "").strip() or None

        return Activity(
            title=title,
            url=row.get("活動網址") or SITE_URL,
            date_start=date_start,
            date_end=date_end,
            location_city="台中市",
            location_address=address,
            age_min=age_min,
            age_max=age_max,
            price=price,
            is_free=is_free,
            summary=f"{title}｜{date_text}｜{address or ''}",
            organizer="台中市政府文化局",
            source=self.name,
        )
