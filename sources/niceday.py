"""Niceday 玩體驗 scraper（民間親子體驗平台）。

Niceday（play.niceday.tw，FunNow 旗下）是全台最大親子體驗預訂平台，
小小店長/小小職人這類品牌職業體驗多在此上架。

策略：
1. 分類/主題頁（小小職人、親子體驗）是 SSR，requests 可直接解析卡片。
2. 站內搜尋（關鍵字「台中」等）是前端渲染，需 Playwright；
   未安裝時只用 SSR 頁面，不中斷。

卡片文字為多行：徽章(熱門/新上架)、標題、店家、行政區、TWD、價格、起。
"""
from __future__ import annotations

import logging
import re
from urllib.parse import quote

from bs4 import BeautifulSoup

from .base import Activity, BaseScraper, parse_age

logger = logging.getLogger("scraper")

BASE = "https://play.niceday.tw"

# SSR 可直接抓的列表頁：小小職人分類、小小職人主題、4~6 歲主題
SSR_PAGES = [
    f"{BASE}/zh-tw/regions/21/categories/13698",
    f"{BASE}/zh-tw/regions/21/themes/11837",
    f"{BASE}/zh-tw/regions/21/themes/11873",
]

# Playwright 搜尋關鍵字（搜尋結果是前端渲染）
SEARCH_KEYWORDS = ["台中", "台中 親子", "小小店長", "小小職人 台中"]
SEARCH_URL = BASE + "/zh-tw/regions/21/search?keyword={kw}"

# 只有台中才有的區名（其他縣市無同名區），可直接認定為台中
TAICHUNG_DISTRICTS_UNIQUE = [
    "西屯區", "南屯區", "北屯區", "豐原區", "潭子區", "大雅區", "神岡區",
    "后里區", "東勢區", "新社區", "石岡區", "外埔區", "清水區", "沙鹿區",
    "梧棲區", "大甲區", "大肚區", "龍井區", "烏日區", "霧峰區",
]
# 各縣市都可能同名的區，需文字中另有「台中」佐證
TAICHUNG_DISTRICTS_AMBIGUOUS = [
    "中區", "東區", "西區", "南區", "北區",
    "大里區", "太平區", "和平區", "大安區",
]

PRICE_RE = re.compile(r"([0-9][0-9,]{1,6})")


def _detect_taichung(text: str) -> str | None:
    """從卡片文字判斷是否為台中活動，是則回傳行政區名。"""
    t = text.replace("臺", "台")
    for d in TAICHUNG_DISTRICTS_UNIQUE:
        if d in t:
            return d
    if "台中" in t:
        for d in TAICHUNG_DISTRICTS_AMBIGUOUS:
            if d in t:
                return d
        return "台中市"
    return None


class NicedayScraper(BaseScraper):
    name = "niceday"

    def scrape(self) -> list[Activity]:
        activities: list[Activity] = []
        seen: set[str] = set()

        for url in SSR_PAGES:
            resp = self.get(url)
            if resp is None:
                continue
            self._collect(resp.text, activities, seen)

        html_pages = self._search_playwright()
        for html in html_pages:
            self._collect(html, activities, seen)

        return activities

    def _collect(self, html: str, out: list[Activity], seen: set[str]) -> None:
        for act in self._parse_cards(html):
            if act.url not in seen:
                seen.add(act.url)
                out.append(act)

    def _parse_cards(self, html: str) -> list[Activity]:
        soup = BeautifulSoup(html, "html.parser")
        out: list[Activity] = []
        for a in soup.select("a[href*='/products/']"):
            try:
                act = self._from_card(a)
                if act:
                    out.append(act)
            except Exception as e:
                self.errors.append(f"[{self.name}] 卡片解析失敗: {e}")
        return out

    def _from_card(self, a) -> Activity | None:
        href = (a.get("href") or "").split("?")[0]
        if not href or "/products/" not in href:
            return None
        if href.startswith("/"):
            href = BASE + href

        lines = [s for s in a.get_text("\n", strip=True).split("\n") if s]
        if not lines:
            return None
        # 標題＝去掉徽章後的第一行
        body = [s for s in lines if s not in ("熱門", "新上架", "TWD", "起")]
        if not body:
            return None
        title = body[0]

        full_text = " ".join(lines)
        district = _detect_taichung(full_text)
        if district is None:
            return None  # 非台中，直接略過

        age_min, age_max = parse_age(title)
        m = PRICE_RE.search(full_text.split("TWD")[-1])
        price = int(m.group(1).replace(",", "")) if m else None
        organizer = body[1] if len(body) > 1 else None

        return Activity(
            title=title,
            url=href,
            # Niceday 多為常態開課，場次日期在內頁，留空由 filter 保留
            location_city="台中市",
            location_address=district if district != "台中市" else None,
            age_min=age_min,
            age_max=age_max,
            price=price,
            is_free=(price == 0) if price is not None else None,
            summary=title,
            organizer=organizer,
            source=self.name,
        )

    def _search_playwright(self) -> list[str]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.errors.append("[niceday] Playwright 未安裝，跳過站內搜尋")
            return []
        pages: list[str] = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                for kw in SEARCH_KEYWORDS:
                    url = SEARCH_URL.format(kw=quote(kw))
                    try:
                        page.goto(url, timeout=45000, wait_until="networkidle")
                        try:
                            page.wait_for_selector(
                                "a[href*='/products/']", timeout=8000
                            )
                        except Exception:
                            pass  # 無結果的關鍵字
                        pages.append(page.content())
                    except Exception as e:
                        self.errors.append(f"[niceday] 搜尋 {kw} 失敗: {e}")
                browser.close()
        except Exception as e:
            self.errors.append(f"[niceday] Playwright 啟動失敗: {e}")
        return pages
