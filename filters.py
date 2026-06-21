"""活動篩選與排序邏輯。"""
from __future__ import annotations

import re
from datetime import date, timedelta

from sources.base import Activity

# 排除關鍵字：純線上 / 演講型
ONLINE_KEYWORDS = ["線上", "直播", "Zoom", "zoom", "Google Meet", "視訊", "webinar", "Webinar"]
LECTURE_KEYWORDS = ["講座", "演講", "論壇", "研討會", "座談"]

# 台中「市區」定義：保留以下核心區，其餘（海線清水/沙鹿/梧棲、
# 山線豐原/東勢、外圍大甲/大雅/霧峰…）一律排除。要放寬就把區名搬過來。
TAICHUNG_URBAN_DISTRICTS = [
    "中區", "東區", "西區", "南區", "北區", "西屯區", "南屯區", "北屯區",
]
TAICHUNG_EXCLUDED_DISTRICTS = [
    "清水區", "沙鹿區", "梧棲區", "大甲區", "大安區", "外埔區",
    "龍井區", "大肚區", "和平區", "東勢區", "新社區", "石岡區",
    "后里區", "神岡區", "大雅區", "潭子區", "豐原區", "霧峰區",
    "太平區", "大里區", "烏日區",
]
# 這些區名夠獨特，文字中沒帶「區」字也視為該區（如「沙鹿圖書館」）
_EXCLUDED_BARE_NAMES = [
    "清水", "沙鹿", "梧棲", "大甲", "外埔", "龍井", "大肚",
    "東勢", "新社", "石岡", "后里", "神岡", "大雅", "潭子",
    "豐原", "霧峰", "烏日", "海線",
]
# 場館名稱不含區名、但位於排除區的知名場館
_EXCLUDED_VENUES = [
    "港區藝術中心",    # 清水
    "葫蘆墩",          # 豐原（文化中心/分館）
    "屯區藝文中心",    # 太平
    "太平分館", "坪林分館",            # 太平
    "大里分館", "大新分館", "德芳分館",  # 大里
    "上楓分館",        # 大雅
]

# 優先保留的體驗型關鍵字 → 對應 tag
PRIORITY_TAGS = {
    "體驗": "體驗課",
    "職業": "職業體驗",
    "小小": "職業體驗",
    "DIY": "DIY手作",
    "手作": "DIY手作",
    "農場": "農場體驗",
    "烹飪": "烹飪課",
    "料理": "烹飪課",
    "藝術": "藝術課",
    "美術": "藝術課",
    "繪畫": "藝術課",
    "感統": "感統課",
}


def _full_text(act: Activity) -> str:
    return " ".join(filter(None, [act.title, act.summary, " ".join(act.tags)]))


def is_online_only(act: Activity) -> bool:
    text = _full_text(act)
    return any(k in text for k in ONLINE_KEYWORDS) and "實體" not in text


def is_lecture_only(act: Activity) -> bool:
    """演講型且無任何互動體驗關鍵字才排除。"""
    text = _full_text(act)
    if not any(k in text for k in LECTURE_KEYWORDS):
        return False
    return not any(k in text for k in PRIORITY_TAGS)


def is_age_suitable(act: Activity, target_min: int = 2, target_max: int = 4) -> bool:
    """排除明確要求 12 歲以上的活動；年齡未標示者保留（人工再確認）。"""
    if act.age_min is not None and act.age_min >= 12:
        return False
    if act.age_max is not None and act.age_max < target_min:
        return False
    return True


def is_within_days(act: Activity, days: int, today: date | None = None) -> bool:
    """活動需落在今天起 N 天內；日期未知者保留（如 KKday 長期體驗）。"""
    today = today or date.today()
    deadline = today + timedelta(days=days)
    if act.date_start is None and act.date_end is None:
        return True
    try:
        start = date.fromisoformat(act.date_start) if act.date_start else None
        end = date.fromisoformat(act.date_end) if act.date_end else start
    except ValueError:
        return True
    if end and end < today:       # 已結束
        return False
    if start and start > deadline:  # 太遠
        return False
    return True


def is_in_target_city(act: Activity, city: str) -> bool:
    """只保留目標縣市的活動；城市未知者需在文字中提到該縣市才保留。"""
    if act.location_city == city:
        return True
    if act.location_city is not None:
        return False
    text = _full_text(act) + " " + (act.location_address or "")
    return city[:2] in text.replace("臺", "台")


def is_in_urban_taichung(act: Activity) -> bool:
    """台中限定：排除海線/山線/外圍區的活動（地址或標題提到就排除）。"""
    text = (act.title or "") + " " + (act.location_address or "") + " " + (act.summary or "")
    if any(d in text for d in TAICHUNG_EXCLUDED_DISTRICTS):
        return False
    if any(name in text for name in _EXCLUDED_BARE_NAMES):
        return False
    if any(v in text for v in _EXCLUDED_VENUES):
        return False
    return True


_DEDUP_NOISE_RE = re.compile(r"[0-9０-９]+|[/.~－—-]|[年月日週梯]|第[一二三四五六七八九十]+[場期堂]")


def _dedup_key(act: Activity) -> tuple[str, str]:
    """同系列活動（每月/每週開課、只差日期場次的標題）歸為同一鍵。"""
    title = _DEDUP_NOISE_RE.sub("", act.title or "")
    title = re.sub(r"\s+", "", title)
    return title, (act.location_address or "")


def dedupe_series(activities: list[Activity]) -> list[Activity]:
    """同名系列只留最早即將舉行的一場，結束日取系列最大值。"""
    groups: dict[tuple[str, str], Activity] = {}
    for act in activities:
        key = _dedup_key(act)
        kept = groups.get(key)
        if kept is None:
            groups[key] = act
            continue
        # 已有同系列：留 date_start 較早者（無日期者視為最晚）
        def start_of(a: Activity) -> str:
            return a.date_start or "9999-12-31"
        winner, loser = (act, kept) if start_of(act) < start_of(kept) else (kept, act)
        if loser.date_end and (not winner.date_end or loser.date_end > winner.date_end):
            winner.date_end = loser.date_end
        groups[key] = winner
    return list(groups.values())


def assign_tags(act: Activity) -> None:
    text = _full_text(act)
    for kw, tag in PRIORITY_TAGS.items():
        if kw in text and tag not in act.tags:
            act.tags.append(tag)
    if any(k in text for k in ("室內", "館", "教室")):
        if "室內" not in act.tags:
            act.tags.append("室內")


def priority_score(act: Activity, preferred_city: str) -> int:
    """排序用分數：城市符合、體驗型 tag、年齡明確標示加分。"""
    score = 0
    if act.location_city == preferred_city:
        score += 100
    # 民間品牌/體驗平台優先於政府場館（避免文化局活動洗版）
    if act.source in ("brands", "niceday"):
        score += 50
    elif act.source in ("pinkoi", "beclass"):
        score += 30
    score += len([t for t in act.tags if t != "室內"]) * 10
    if act.age_min is not None:
        score += 5
    if act.date_start is not None:
        score += 5
    return score


def filter_and_rank(
    activities: list[Activity],
    city: str = "台中市",
    days: int = 60,
) -> list[Activity]:
    kept = []
    for act in activities:
        if is_online_only(act):
            continue
        if is_lecture_only(act):
            continue
        if not is_age_suitable(act):
            continue
        if not is_within_days(act, days):
            continue
        if not is_in_target_city(act, city):
            continue
        if city == "台中市" and not is_in_urban_taichung(act):
            continue
        assign_tags(act)
        kept.append(act)
    kept = dedupe_series(kept)
    kept.sort(key=lambda a: priority_score(a, city), reverse=True)
    return kept
