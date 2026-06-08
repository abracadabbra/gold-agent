"""JSON 序列化工具函数"""

from typing import Any

import numpy as np
import pandas as pd


def json_safe(df: pd.DataFrame) -> list[dict[str, Any]]:
    """将 DataFrame 转为 JSON-safe 字典列表，NaN/NaT/Inf 替换为 None"""
    if df.empty:
        return []
    df = df.where(df.notna(), np.nan)
    result = df.astype(object).where(df.notna(), np.nan).to_dict(orient="records")
    for row in result:
        for k, v in row.items():
            if isinstance(v, float) and (np.isinf(v) or np.isnan(v)):
                row[k] = None
    return result  # type: ignore[return-value]
