"""财经日历 — 重大经济事件（当前为 mock 数据）"""

import pandas as pd
from datetime import timedelta

# Mock 数据：未来 6 个月的重大财经事件
# type 缩写: E=Employment, Ec=Economic, C=China, F=FOMC
MOCK_EVENTS = [
    {"date": "2026-05-21", "event": "FOMC 会议纪要", "importance": "high", "type": "FOMC"},
    {"date": "2026-05-23", "event": "美国 CPI 数据发布", "importance": "high", "type": "Ec"},
    {"date": "2026-05-27", "event": "美国非农就业", "importance": "very_high", "type": "E"},
    {"date": "2026-05-30", "event": "中国 PMI 制造业", "importance": "high", "type": "C"},
    # 2026 年 6 月
    {"date": "2026-06-04", "event": "FOMC 利率决议", "importance": "very_high", "type": "FOMC"},
    {"date": "2026-06-11", "event": "美国 CPI 数据发布", "importance": "high", "type": "Ec"},
    {"date": "2026-06-13", "event": "中国 M2 货币供应", "importance": "medium", "type": "C"},
    {"date": "2026-06-18", "event": "美国零售销售", "importance": "high", "type": "Ec"},
    {"date": "2026-06-25", "event": "美国非农就业", "importance": "very_high", "type": "E"},
    {"date": "2026-06-27", "event": "中国 PMI 制造业", "importance": "high", "type": "C"},
    # 2026 年 7 月
    {"date": "2026-07-01", "event": "FOMC 会议纪要", "importance": "high", "type": "FOMC"},
    {"date": "2026-07-09", "event": "中国 CPI/PPI", "importance": "high", "type": "C"},
    {"date": "2026-07-14", "event": "美国 CPI 数据发布", "importance": "high", "type": "Ec"},
    {"date": "2026-07-24", "event": "FOMC 利率决议", "importance": "very_high", "type": "FOMC"},
    {"date": "2026-07-30", "event": "美国非农就业", "importance": "very_high", "type": "E"},
    # 2026 年 8 月
    {"date": "2026-08-05", "event": "中国 PMI 制造业", "importance": "high", "type": "C"},
    {"date": "2026-08-12", "event": "美国 CPI 数据发布", "importance": "high", "type": "Ec"},
    {"date": "2026-08-21", "event": "FOMC 会议纪要", "importance": "high", "type": "FOMC"},
    {"date": "2026-08-27", "event": "美国非农就业", "importance": "very_high", "type": "E"},
    # 2026 年 9 月
    {"date": "2026-09-02", "event": "中国 PMI 制造业", "importance": "high", "type": "C"},
    {"date": "2026-09-10", "event": "美国 CPI 数据发布", "importance": "high", "type": "Ec"},
    {"date": "2026-09-17", "event": "FOMC 利率决议", "importance": "very_high", "type": "FOMC"},
    {"date": "2026-09-26", "event": "美国非农就业", "importance": "very_high", "type": "E"},
]

IMPORTANCE_COLORS = {
    "very_high": "#dc2626",
    "high": "#f59e0b",
    "medium": "#3b82f6",
    "low": "#6b7280",
}

EVENT_TYPE_LABELS = {
    "FOMC": "美联储决议",
    "E": "就业数据",
    "Ec": "经济数据",
    "C": "中国数据",
}


def fetch_calendar(start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
    """获取财经日历"""
    df = pd.DataFrame(MOCK_EVENTS)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # 添加颜色和标签
    df["color"] = df["importance"].map(IMPORTANCE_COLORS)
    df["type_label"] = df["type"].map(EVENT_TYPE_LABELS)

    # 过滤日期范围
    if start_date:
        df = df[df["date"] >= pd.to_datetime(start_date)]
    if end_date:
        df = df[df["date"] <= pd.to_datetime(end_date)]

    return df


def get_upcoming_events(days: int = 14) -> pd.DataFrame:
    """获取未来 N 天的即将到来的事件"""
    today = pd.Timestamp.now().normalize()
    end = today + timedelta(days=days)
    return fetch_calendar(start_date=today.strftime("%Y-%m-%d"), end_date=end.strftime("%Y-%m-%d"))


def get_next_major_event() -> dict | None:
    """获取下一个重大事件"""
    upcoming = get_upcoming_events(30)
    if upcoming.empty:
        return None

    # 返回最高优先级
    priority_order = {"very_high": 0, "high": 1, "medium": 2, "low": 3}
    upcoming["priority_num"] = upcoming["importance"].map(priority_order)
    next_event = upcoming.sort_values("priority_num").iloc[0]

    return {
        "date": next_event["date"].strftime("%Y-%m-%d"),
        "event": next_event["event"],
        "type": next_event["type"],
        "type_label": next_event["type_label"],
        "importance": next_event["importance"],
        "color": next_event["color"],
    }
