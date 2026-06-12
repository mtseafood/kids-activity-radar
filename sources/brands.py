"""民間品牌職業體驗 scraper（麥當勞、Mister Donut、全家…）。

這類體驗不在活動平台上架，而是品牌自辦、透過官方管道預約：
- 麥當勞「小麥麥體驗營」：寒暑假限定，麥當勞 APP 報名，秒殺型。
- Mister Donut「小小烘焙師」：官網 DIY 教室頁有各門市場次，可直接解析。
- 全家便利商店「小小店長體驗營」：每月於各店舖報名。

麥當勞/全家無結構化場次資料，以固定條目呈現（附官方報名連結），
並 GET 官方頁確認還活著；Mister Donut 則解析官網的台中門市場次。
"""
from __future__ import annotations

import logging
import re
from datetime import date

from bs4 import BeautifulSoup

from .base import Activity, BaseScraper

logger = logging.getLogger("scraper")

MCD_URL = "https://fun.mcdonalds.com.tw/camp.html"
MDO_URL = (
    "https://www.misterdonut.com.tw/ContentDetail/"
    "%E3%80%90DIY%E6%95%99%E5%AE%A4%E3%80%91%E5%B0%8F%E5%B0%8F%E7%83%98"
    "%E7%84%99%E5%B8%AB%E9%96%8B%E8%AA%B2%E4%B8%AD%EF%BC%81-2010200001-221"
)
FAMI_URL = "https://www.family.com.tw/NewEnterprise/CSR/Care/Article/13"

MD_DATE_RE = re.compile(r"(\d{1,2})/(\d{1,2})")


class BrandExperienceScraper(BaseScraper):
    name = "brands"

    def scrape(self) -> list[Activity]:
        activities: list[Activity] = []
        activities.extend(self._static_entries())
        activities.extend(self._mister_donut())
        return activities

    def _static_entries(self) -> list[Activity]:
        """無結構化場次的品牌體驗：固定條目＋官方頁存活確認。"""
        entries = [
            Activity(
                title="麥當勞 小麥麥體驗營（小小經理職業體驗）",
                url=MCD_URL,
                location_city="台中市",
                location_address="台中各參與門市（報名時選擇）",
                age_min=3,
                price=988,
                is_free=False,
                summary="寒暑假限定，收銀/飲料快手等工作體驗＋小麥麥家家酒組。"
                        "透過麥當勞 APP 報名，開放即秒殺（7月場 6/1 起、8月場 7/6 起報名）",
                organizer="台灣麥當勞",
                tags=["職業體驗"],
                source=self.name,
            ),
            Activity(
                title="全家便利商店 小小店長體驗營",
                url=FAMI_URL,
                location_city="台中市",
                location_address="台中各舉辦店舖",
                age_min=3,
                summary="每月開課，學習收銀、補貨、咖啡拉花等店務體驗。"
                        "每月 30 日後向住家附近全家店舖詢問次月場次並報名",
                organizer="全家便利商店",
                tags=["職業體驗"],
                source=self.name,
            ),
        ]
        for act in entries:
            resp = self.get(act.url)
            if resp is None:
                act.summary += "（官方頁面暫時無法連線，報名前請先確認）"
        return entries

    def _mister_donut(self) -> list[Activity]:
        """解析 Mister Donut 官網 DIY 教室頁的台中門市場次。"""
        resp = self.get(MDO_URL)
        if resp is None:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text("\n", strip=True)

        out: list[Activity] = []
        # 門市區塊以「※ 如欲報名請致電向該門市詢問！」分隔，
        # 欄位格式：門市名 / 日期｜… / 場次｜… / 電話｜… / 地址｜…
        for block in text.split("※"):
            if "台中市" not in block:
                continue
            lines = [s.strip() for s in block.split("\n") if s.strip()]
            store = next((s for s in lines if s.endswith("門市")), None)
            if store is None:
                continue
            date_line = next((s for s in lines if s.startswith("日期")), "")
            addr = next(
                (s for s in lines if "台中市" in s and "地址" not in s), None
            ) or next((s for s in lines if "台中市" in s), None)
            if addr and addr.startswith("地址"):
                addr = addr.split("｜", 1)[-1].strip()

            date_start, date_end = self._parse_md_dates(date_line)
            session_note = date_line.split("｜", 1)[-1] if "｜" in date_line else ""
            if date_start is None:
                session_note = ""  # 官網日期已過期或未公布，避免誤導
            out.append(Activity(
                title=f"Mister Donut 小小烘焙師 甜甜圈DIY（{store}）",
                url=MDO_URL,
                date_start=date_start,
                date_end=date_end,
                location_city="台中市",
                location_address=addr,
                age_min=3,
                price=700,
                is_free=False,
                summary=f"穿小小烘焙師制服裝飾甜甜圈，{store}。"
                        f"場次：{session_note or '請致電門市詢問'}，電話/粉專報名",
                organizer="Mister Donut 統一多拿滋",
                tags=["DIY手作", "職業體驗"],
                source=self.name,
            ))
        return out

    def _parse_md_dates(self, text: str) -> tuple[str | None, str | None]:
        """解析「5/23、5/30」這類無年份日期；全部已過期則視為待公告。"""
        today = date.today()
        dates = []
        for m in MD_DATE_RE.finditer(text):
            month, day = int(m.group(1)), int(m.group(2))
            try:
                d = date(today.year, month, day)
            except ValueError:
                continue
            if d < today:
                # 可能是明年初的場次（如 12 月看到 1/15）；半年內的過期日期視為舊資料
                if (today - d).days > 180:
                    d = date(today.year + 1, month, day)
                else:
                    continue
            dates.append(d)
        if not dates:
            return None, None
        return min(dates).isoformat(), max(dates).isoformat()
