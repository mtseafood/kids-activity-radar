"""共用基底：Activity 資料結構、HTTP session、禮貌性延遲、錯誤記錄。"""
from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Optional

import requests

logger = logging.getLogger("scraper")

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

# 縣市正規化：把「臺中市 / 台中 / Taichung」都對應到「台中市」
TW_CITIES = [
    "台北市", "新北市", "基隆市", "桃園市", "新竹市", "新竹縣", "苗栗縣",
    "台中市", "彰化縣", "南投縣", "雲林縣", "嘉義市", "嘉義縣", "台南市",
    "高雄市", "屏東縣", "宜蘭縣", "花蓮縣", "台東縣", "澎湖縣", "金門縣", "連江縣",
]


# 英文城市名對照（Accupass 等網站使用英文地名）
EN_CITY_MAP = {
    "Taipei": "台北市", "New Taipei": "新北市", "Keelung": "基隆市",
    "Taoyuan": "桃園市", "Hsinchu": "新竹市", "Miaoli": "苗栗縣",
    "Taichung": "台中市", "Changhua": "彰化縣", "Nantou": "南投縣",
    "Yunlin": "雲林縣", "Chiayi": "嘉義市", "Tainan": "台南市",
    "Kaohsiung": "高雄市", "Pingtung": "屏東縣", "Yilan": "宜蘭縣",
    "Hualien": "花蓮縣", "Taitung": "台東縣", "Penghu": "澎湖縣",
    "Kinmen": "金門縣",
}


def normalize_city(text: str) -> Optional[str]:
    """從任意文字中找出縣市名稱，回傳正規化後的「台X市」寫法。"""
    if not text:
        return None
    t = text.replace("臺", "台")
    for city in TW_CITIES:
        if city[:2] in t:
            return city
    for en, zh in EN_CITY_MAP.items():
        if en in text:
            return zh
    return None


@dataclass
class Activity:
    title: str
    url: str
    date_start: Optional[str] = None  # ISO: YYYY-MM-DD
    date_end: Optional[str] = None
    location_city: Optional[str] = None
    location_address: Optional[str] = None
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    price: Optional[int] = None
    is_free: Optional[bool] = None
    summary: str = ""
    organizer: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    source: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["summary"] = (self.summary or "")[:100]
        return d


DATE_RE = re.compile(r"(20\d{2})[./\-年](\d{1,2})[./\-月](\d{1,2})")


def parse_date(text: str) -> Optional[str]:
    """從文字中抓出第一個日期，回傳 ISO 格式字串。"""
    if not text:
        return None
    m = DATE_RE.search(text)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return None


def parse_date_range(text: str) -> tuple[Optional[str], Optional[str]]:
    """抓出文字中的所有日期，回傳 (最早, 最晚)。"""
    if not text:
        return None, None
    dates = []
    for m in DATE_RE.finditer(text):
        try:
            dates.append(date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
        except ValueError:
            continue
    if not dates:
        return None, None
    return min(dates).isoformat(), max(dates).isoformat()


AGE_RANGE_RE = re.compile(r"(\d{1,2})\s*[-~～至到]\s*(\d{1,2})\s*歲")
AGE_MIN_RE = re.compile(r"(\d{1,2})\s*歲(?:以上|起|\+)")


def parse_age(text: str) -> tuple[Optional[int], Optional[int]]:
    """從文字中解析適合年齡，回傳 (age_min, age_max)。"""
    if not text:
        return None, None
    m = AGE_RANGE_RE.search(text)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = AGE_MIN_RE.search(text)
    if m:
        return int(m.group(1)), None
    return None, None


PRICE_RE = re.compile(r"(?:NT\$|NTD|\$|新台幣|新臺幣)?\s*([0-9,]{2,7})\s*(?:元|起)?")


def parse_price(text: str) -> tuple[Optional[int], Optional[bool]]:
    """回傳 (price, is_free)。"""
    if not text:
        return None, None
    if any(k in text for k in ("免費", "Free", "free", "不收費")):
        return 0, True
    m = PRICE_RE.search(text)
    if m:
        try:
            price = int(m.group(1).replace(",", ""))
            return price, price == 0
        except ValueError:
            pass
    return None, None


class BaseScraper:
    """各來源 scraper 的基底類別。子類別實作 scrape()。"""

    name = "base"

    def __init__(self, city: str = "台中市", days: int = 60):
        self.city = city
        self.days = days
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        })
        self.errors: list[str] = []

    def sleep(self):
        """禮貌性隨機延遲 1~3 秒。"""
        time.sleep(random.uniform(1.0, 3.0))

    def get(self, url: str, **kwargs) -> Optional[requests.Response]:
        """安全的 GET：失敗時記錄錯誤並回傳 None，不中斷流程。"""
        try:
            resp = self.session.get(url, timeout=20, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            msg = f"[{self.name}] GET {url} 失敗: {e}"
            logger.error(msg)
            self.errors.append(msg)
            return None
        finally:
            self.sleep()

    def scrape(self) -> list[Activity]:
        raise NotImplementedError
