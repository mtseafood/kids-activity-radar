"""活動篩選與排序邏輯。"""
from __future__ import annotations

from datetime import date, timedelta

from sources.base import Activity

# 排除關鍵字：純線上 / 演講型
ONLINE_KEYWORDS = ["線上", "直播", "Zoom", "zoom", "Google Meet", "視訊", "webinar", "Webinar"]
LECTURE_KEYWORDS = ["講座", "演講", "論壇", "研討會", "座談"]

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
        assign_tags(act)
        kept.append(act)
    kept.sort(key=lambda a: priority_score(a, city), reverse=True)
    return kept
