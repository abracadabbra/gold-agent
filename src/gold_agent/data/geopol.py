"""地缘政治风险指数 (GPR Index) — matteoiacoviello.com 静态 XLS"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

GPR_URL = "https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls"


def fetch_geopol(variant: str = "global") -> pd.DataFrame:
    """
    下载 GPR 指数数据

    Args:
        variant: "global" (全球总指数) 或国家代码

    Returns:
        DataFrame: date, gpr_index, gpr_threats, gpr_acts
    """
    try:
        df = pd.read_excel(GPR_URL, engine="xlrd")
        logger.info(f"[geopol] 下载成功: {df.shape}")

        # 标准化列名 — 小写、去空格
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        # 找日期列并转换为 datetime
        date_cols = [c for c in df.columns if "date" in c or "year" in c or "month" in c]
        if not date_cols:
            logger.warning("[geopol] 未找到日期列")
            return pd.DataFrame()

        if "date" not in df.columns and len(date_cols) >= 2:
            # 尝试组合 year + month
            df["date"] = pd.to_datetime(
                df[date_cols[0]].astype(int).astype(str)
                + "-"
                + df[date_cols[1]].astype(int).astype(str).str.zfill(2)
                + "-01"
            )
        elif "date" not in df.columns:
            df["date"] = pd.to_datetime(df[date_cols[0]])

        if "date" not in df.columns:
            logger.warning("[geopol] 无法构造日期列")
            return pd.DataFrame()

        # 找到 GPR 指数列
        gpr_cols = {
            "gpr_index": [
                c for c in df.columns
                if "gpr" in c and "threat" not in c and "act" not in c and c != "date"
            ],
            "gpr_threats": [c for c in df.columns if "threat" in c],
            "gpr_acts": [c for c in df.columns if "act" in c],
        }

        result_cols = ["date"]
        for key, candidates in gpr_cols.items():
            if candidates:
                result_cols.append(candidates[0])

        result = df[result_cols].copy()
        rename_cols = {result_cols[1]: "gpr_index"} if len(result_cols) > 1 else {}
        result = result.rename(columns=rename_cols)

        # 将 threat/act 列统一命名为 gpr_threats / gpr_acts
        threat_act_map = {}
        for c in result.columns:
            if c != "date" and c != "gpr_index":
                if "threat" in c:
                    threat_act_map[c] = "gpr_threats"
                elif "act" in c:
                    threat_act_map[c] = "gpr_acts"
        if threat_act_map:
            result = result.rename(columns=threat_act_map)

        result = result.sort_values("date").reset_index(drop=True)
        logger.info(f"[geopol] 处理完成: {len(result)} 行, 列={list(result.columns)}")
        return result

    except Exception as e:
        logger.warning(f"[geopol] 下载失败: {e}")
        return pd.DataFrame()
