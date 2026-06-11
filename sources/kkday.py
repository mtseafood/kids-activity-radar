"""KKday scraper。

KKday 全站受 DataDome 反爬蟲保護，純 requests 會被擋 403。
流程：先嘗試 ajax JSON API（被擋時自動偵測），失敗則退回
Playwright 以真實瀏覽器渲染搜尋頁。若 Playwright 也被驗證頁
攔下，會記錄錯誤並跳過此來源（不中斷其他來源）。
"""
from __future__ import annotations

import logging

from .base import (
    Activity, BaseScraper, normalize_city,
    parse_age, parse_price,
)

logger = logging.getLogger("scraper")

# KKday 前端商品列表 API（隨改版可能變動）
API_URL = "https://www.kkday.com/zh-tw/product/ajax_productlist"

SEARCH_KEYWORDS = ["親子", "親子 DIY", "幼兒 體驗"]


class KKdayScraper(BaseScraper):
    name = "kkday"

    def scrape(self) -> list[Activity]:
        activities: list[Activity] = []
        seen: set[str] = set()
        for kw in SEARCH_KEYWORDS:
            items = self._search_api(kw)
            if items is None:
                logger.warning("[kkday] API 失敗，改用 Playwright")
                items = self._search_playwright(kw)
            for act in items:
                if act.url not in seen:
                    seen.add(act.url)
                    activities.append(act)
        return activities

    def _search_api(self, keyword: str) -> list[Activity] | None:
        resp = self.get(API_URL, params={
            "keyword": keyword,
            "country": "A01-001",  # 台灣
            "page": 1,
            "count": 50,
            "sort": "prec",
        })
        if resp is None:
            return None
        try:
            data = resp.json()
        except ValueError:
            return None

        products = data.get("data") or data.get("products") or []
        if not isinstance(products, list):
            return None

        out = []
        for item in products:
            try:
                out.append(self._from_api_item(item))
            except Exception as e:
                self.errors.append(f"[kkday] 解析失敗: {e}")
        return out

    def _from_api_item(self, item: dict) -> Activity:
        url = item.get("url") or item.get("prod_url") or ""
        if url.startswith("/"):
            url = "https://www.kkday.com" + url
        title = item.get("name") or item.get("prod_name") or ""
        intro = item.get("introduction") or item.get("desc") or ""
        city_text = item.get("city") or item.get("city_name") or ""
        price_raw = item.get("price") or item.get("display_price") or ""
        price, is_free = parse_price(str(price_raw))
        age_min, age_max = parse_age(title + " " + intro)
        return Activity(
            title=title,
            url=url,
            # KKday 商品多為長期販售體驗，無固定起迄日，留空由 filter 保留
            location_city=normalize_city(city_text) or normalize_city(title),
            location_address=city_text or None,
            age_min=age_min,
            age_max=age_max,
            price=price,
            is_free=is_free,
            summary=intro,
            organizer="KKday 合作商家",
            source=self.name,
        )

    def _search_playwright(self, keyword: str) -> list[Activity]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.errors.append("[kkday] Playwright 未安裝，跳過 fallback")
            return []

        url = f"https://www.kkday.com/zh-tw/product/productlist?keyword={keyword}"
        out: list[Activity] = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, timeout=30000, wait_until="networkidle")
                cards = page.query_selector_all("a[href*='/product/']")
                for card in cards[:50]:
                    href = card.get_attribute("href") or ""
                    text = (card.inner_text() or "").strip()
                    if not href or not text or "/productlist" in href:
                        continue
                    if href.startswith("/"):
                        href = "https://www.kkday.com" + href
                    age_min, age_max = parse_age(text)
                    price, is_free = parse_price(text)
                    out.append(Activity(
                        title=text.split("\n")[0][:80],
                        url=href,
                        location_city=normalize_city(text),
                        age_min=age_min,
                        age_max=age_max,
                        price=price,
                        is_free=is_free,
                        summary=text,
                        organizer="KKday 合作商家",
                        source=self.name,
                    ))
                browser.close()
        except Exception as e:
            self.errors.append(f"[kkday] Playwright 抓取失敗: {e}")
        return out
