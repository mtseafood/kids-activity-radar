"""Pinkoi 體驗 scraper（民間手作工作坊）。

Pinkoi 的搜尋有公開 JSON API（/apiv2/search），可用
category=15（體驗課程）+ item_location=TW-TXG（台中）直接過濾，
回傳 Elasticsearch 格式的 hits，不需要解析 HTML。

商品多為常態開課的工作坊（陶藝、皮革、琉璃…），無固定日期，
場次在內頁與店家確認。
"""
from __future__ import annotations

import logging

from .base import Activity, BaseScraper, parse_age

logger = logging.getLogger("scraper")

API_URL = "https://www.pinkoi.com/apiv2/search"
PRODUCT_URL = "https://www.pinkoi.com/product/{tid}"

# 只用親子相關查詢——Pinkoi 搜尋是以完整商品描述比對，
# API 不回傳完整描述，故信任站方的關鍵字相關性，不再自行過濾
SEARCH_KEYWORDS = ["親子", "兒童"]
# Pinkoi 的 ISO 3166-2 地區碼：TW-TXG = 台中市
LOCATION = "TW-TXG"
CATEGORY_EXPERIENCE = 15


class PinkoiScraper(BaseScraper):
    name = "pinkoi"

    def scrape(self) -> list[Activity]:
        activities: list[Activity] = []
        seen: set[str] = set()
        for kw in SEARCH_KEYWORDS:
            resp = self.get(API_URL, params={
                "q": kw,
                "category": CATEGORY_EXPERIENCE,
                "item_location": LOCATION,
            })
            if resp is None:
                continue
            try:
                hits = resp.json()["result"][0]["hits"]["hits"]
            except (ValueError, KeyError, IndexError) as e:
                self.errors.append(f"[{self.name}] API 回應解析失敗({kw}): {e}")
                continue
            for hit in hits:
                try:
                    act = self._from_hit(hit)
                    if act and act.url not in seen:
                        seen.add(act.url)
                        activities.append(act)
                except Exception as e:
                    self.errors.append(f"[{self.name}] 單筆解析失敗: {e}")
        return activities

    def _from_hit(self, hit: dict) -> Activity | None:
        fields = hit.get("fields") or {}
        title = (fields.get("title") or "").strip()
        tid = hit.get("_id")
        if not title or not tid:
            return None
        # 保險起見再確認是台中的體驗類商品
        exp_info = fields.get("exp_info") or {}
        location = (exp_info.get("location_name") or "").replace("臺", "台")
        if "台中" not in location:
            return None

        price = fields.get("price")
        age_min, age_max = parse_age(title)
        return Activity(
            title=title,
            url=PRODUCT_URL.format(tid=tid),
            # 常態開課工作坊，場次與店家約定，無固定日期
            location_city="台中市",
            age_min=age_min,
            age_max=age_max,
            price=int(price) if price is not None else None,
            is_free=(price == 0) if price is not None else None,
            summary=title,
            organizer=fields.get("shop_name") or fields.get("owner"),
            tags=["DIY手作"],
            source=self.name,
        )
