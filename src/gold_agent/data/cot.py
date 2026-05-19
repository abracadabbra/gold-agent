"""CFTC COT 持仓报告 — cot_reports 库"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

# COMEX 黄金期货的市场代码
GOLD_MARKET_CODE = "088691"


def fetch_cot(year: int | None = None) -> pd.DataFrame:
    """
    获取 COMEX 黄金期货持仓报告

    Args:
        year: 年份，默认当年

    Returns:
        DataFrame: date, exchange, commodity, open_interest,
                   producer_long, producer_short,
                   swap_long, swap_short,
                   managed_money_long, managed_money_short,
                   other_long, other_short
    """
    try:
        from cot_reports import cot_year

        if year is None:
            import datetime
            year = datetime.date.today().year

        df = cot_year(year=year, cot_report_type="legacy_fut")
        logger.info(f"[cot] 原始 {year} 年数据: {df.shape}")

        if df.empty:
            logger.warning("[cot] 返回空数据")
            return pd.DataFrame()

        # 过滤黄金市场
        if "Market and Exchange Names" in df.columns:
            col = "Market and Exchange Names"
            gold = df[df[col].astype(str).str.contains("GOLD", case=False, na=False)]  # noqa: E501
            if gold.empty:
                gold = df[df["CFTC Commodity Code"].astype(str) == GOLD_MARKET_CODE]
        elif "CFTC_Commodity_Code" in df.columns:
            gold = df[df["CFTC_Commodity_Code"].astype(str) == GOLD_MARKET_CODE]
        elif "commodity_code" in df.columns:
            gold = df[df["commodity_code"].astype(str) == GOLD_MARKET_CODE]
        else:
            # 尝试代码列
            code_cols = [c for c in df.columns if "code" in c.lower() or "market" in c.lower()]
            if code_cols:
                gold = df[df[code_cols[0]].astype(str).str.contains("088691|GOLD", na=False)]
            else:
                logger.warning("[cot] 无法识别市场代码列，使用全部数据")
                gold = df

        if gold.empty:
            logger.warning("[cot] 未找到黄金持仓数据")
            return pd.DataFrame()

        # 标准化列名
        col_map = {
            "Date": "date",
            "date": "date",
            "Market and Exchange Names": "exchange",
            "Open Interest": "open_interest",
            "Prod Long": "producer_long",
            "Prod Short": "producer_short",
            "Swap Long": "swap_long",
            "Swap Short": "swap_short",
            "M M Long": "managed_money_long",
            "M M Short": "managed_money_short",
            "Other Long": "other_long",
            "Other Short": "other_short",
        }

        # 尝试匹配列名（忽略大小写、空格）
        rename = {}
        for col in gold.columns:
            col_clean = col.strip()
            if col_clean in col_map:
                rename[col] = col_map[col_clean]
            else:
                lower = col_clean.lower().replace(" ", "_")
                for k, v in col_map.items():
                    if lower == k.lower().replace(" ", "_") or lower == k.lower():
                        rename[col] = v
                        break

        result = gold.rename(columns=rename)

        # 确保标准列存在
        std_cols = ["date", "exchange", "open_interest",
                    "producer_long", "producer_short",
                    "swap_long", "swap_short",
                    "managed_money_long", "managed_money_short",
                    "other_long", "other_short"]
        available = [c for c in std_cols if c in result.columns]

        result = result[available].copy()

        if "date" in result.columns:
            result["date"] = pd.to_datetime(result["date"], errors="coerce")
            result = result.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

        # 数值列转换
        numeric_cols = [c for c in result.columns if c != "date" and c != "exchange"]
        for c in numeric_cols:
            result[c] = pd.to_numeric(result[c], errors="coerce")

        logger.info(f"[cot] 黄金持仓: {len(result)} 行, 列={list(result.columns)}")
        return result

    except ImportError:
        logger.warning("[cot] cot_reports 未安装，返回空")
        return pd.DataFrame()
    except Exception as e:
        logger.warning(f"[cot] 获取失败: {e}")
        return pd.DataFrame()
