"""央行黄金储备 — 静态快照（IMF IFS 最新发布数据）

源数据：IMF International Financial Statistics / World Gold Council
最后更新：2025-07（数据截至 2025-05）
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

COUNTRY_NAMES = {
    "US": "美国", "DE": "德国", "FR": "法国", "IT": "意大利", "RU": "俄罗斯",
    "CN": "中国", "CH": "瑞士", "IN": "印度", "JP": "日本", "PL": "波兰",
    "NL": "荷兰", "TR": "土耳其", "PT": "葡萄牙", "UZ": "乌兹别克", "TW": "台湾",
    "KZ": "哈萨克", "SA": "沙特", "GB": "英国", "LB": "黎巴嫩", "ES": "西班牙",
    "AT": "奥地利", "TH": "泰国", "EG": "埃及", "BE": "比利时", "PH": "菲律宾",
    "CZ": "捷克", "SE": "瑞典", "ZA": "南非", "SG": "新加坡", "IQ": "伊拉克",
    "AU": "澳大利亚", "KW": "科威特", "ID": "印尼", "AE": "阿联酋",
}

# 各国黄金储备（吨），源：WGC 基于 IMF IFS 2025-07 版
CENTRAL_BANK_RESERVES: list[dict] = [
    {"country": "US", "tonnes": 8133.5}, {"country": "DE", "tonnes": 3710.0},
    {"country": "FR", "tonnes": 2809.8}, {"country": "IT", "tonnes": 2451.8},
    {"country": "RU", "tonnes": 2332.0}, {"country": "CN", "tonnes": 2140.0},
    {"country": "CH", "tonnes": 1040.0}, {"country": "IN", "tonnes": 844.0},
    {"country": "JP", "tonnes": 765.2},  {"country": "PL", "tonnes": 645.0},
    {"country": "NL", "tonnes": 612.5},  {"country": "TR", "tonnes": 574.0},
    {"country": "PT", "tonnes": 504.8},  {"country": "UZ", "tonnes": 500.0},
    {"country": "TW", "tonnes": 423.6},  {"country": "KZ", "tonnes": 404.0},
    {"country": "SA", "tonnes": 323.1},  {"country": "GB", "tonnes": 310.3},
    {"country": "LB", "tonnes": 286.8},  {"country": "ES", "tonnes": 281.6},
    {"country": "AT", "tonnes": 280.0},  {"country": "TH", "tonnes": 242.8},
    {"country": "EG", "tonnes": 240.0},  {"country": "BE", "tonnes": 227.4},
    {"country": "PH", "tonnes": 200.0},  {"country": "CZ", "tonnes": 197.6},
    {"country": "SE", "tonnes": 185.0},  {"country": "ZA", "tonnes": 125.3},
    {"country": "SG", "tonnes": 127.4},  {"country": "IQ", "tonnes": 90.0},
    {"country": "AU", "tonnes": 79.8},   {"country": "KW", "tonnes": 79.0},
    {"country": "ID", "tonnes": 78.6},   {"country": "AE", "tonnes": 74.6},
]


def fetch_central_bank_reserves(
    countries: list[str] | None = None,
    start_year: int = 2020,
) -> pd.DataFrame:
    """获取央行黄金储备"""
    df = pd.DataFrame(CENTRAL_BANK_RESERVES)
    df["date"] = "2025-05-01"
    df["date"] = pd.to_datetime(df["date"])
    df["country_name"] = df["country"].map(COUNTRY_NAMES)
    df = df.rename(columns={"tonnes": "gold_reserves_tonnes"})

    if countries:
        df = df[df["country"].isin(countries)]

    df = df.sort_values("gold_reserves_tonnes", ascending=False).reset_index(drop=True)
    df["rank"] = range(1, len(df) + 1)

    logger.info(f"[central_bank] 返回 {len(df)} 条记录")
    return df
