"""JSON 序列化工具函数"""

from typing import Any

import pandas as pd


def json_safe(df: pd.DataFrame) -> list[dict[str, Any]]:
    """将 DataFrame 转为 JSON-safe 字典列表，NaN/NaT 替换为 None"""
    if df.empty:
        return []
    return df.where(df.notna(), None).astype(object).where(df.notna(), None).to_dict(
        orient="records",
    )
