"""CME FedWatch 利率预期 — cme-fedwatch 库"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def fetch_fedwatch() -> pd.DataFrame:
    """
    获取 FOMC 会议利率概率

    Returns:
        DataFrame: meeting_date, current_rate, cut_prob, hold_prob, hike_prob
    """
    try:
        from cme_fedwatch import get_probabilities

        data = get_probabilities("all")
        logger.info("[fedwatch] 获取成功")

        if not data:
            logger.warning("[fedwatch] 返回空数据")
            return pd.DataFrame()

        # cme-fedwatch 返回 list[dict] 或 dict
        if isinstance(data, dict):
            records = [data]
        else:
            records = data

        rows = []
        for item in records:
            meeting_date = item.get("meetingDate", item.get("date", ""))
            current_rate = item.get("currentRate", item.get("current_rate", None))
            probs = item.get("probabilities", item)
            row = {
                "meeting_date": meeting_date,
                "current_rate": current_rate,
                "cut_prob": probs.get("cut", probs.get("-25", 0)) if isinstance(probs, dict) else 0,
                "hold_prob": probs.get("hold", probs.get("0", 0)) if isinstance(probs, dict) else 0,
                "hike_prob": (
                    probs.get("hike", probs.get("+25", 0))
                    if isinstance(probs, dict) else 0
                ),
            }
            rows.append(row)

        df = pd.DataFrame(rows)
        if "meeting_date" in df.columns:
            df["date"] = pd.to_datetime(df["meeting_date"], errors="coerce")
        df = df.sort_values("date").reset_index(drop=True) if "date" in df.columns else df

        logger.info(f"[fedwatch] 处理完成: {len(df)} 行")
        return df

    except ImportError:
        logger.warning("[fedwatch] cme-fedwatch 未安装，返回空")
        return pd.DataFrame()
    except Exception as e:
        logger.warning(f"[fedwatch] 获取失败: {e}")
        return pd.DataFrame()
