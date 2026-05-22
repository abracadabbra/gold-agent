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

        data = get_probabilities()
        logger.info("[fedwatch] 获取成功")

        if not data:
            logger.warning("[fedwatch] 返回空数据")
            return pd.DataFrame()

        # cme-fedwatch 返回 {effr, current_target, meetings: [{date, contract, probabilities}]}
        meetings = data.get("meetings", data if isinstance(data, list) else [data])
        if isinstance(meetings, dict):
            meetings = [meetings]

        current_target = data.get("current_target", "")
        cur_low = float(current_target.split("-")[0].rstrip("%")) if current_target and "-" in current_target else 0
        cur_high = float(current_target.split("-")[1].rstrip("%")) if current_target and "-" in current_target else 0
        rows = []
        for item in meetings:
            meeting_date = item.get("date", "")
            probs = item.get("probabilities", {})
            cut_prob = hold_prob = hike_prob = 0.0
            for rate_range, prob in probs.items():
                if "-" not in rate_range:
                    continue
                r_low = float(rate_range.split("-")[0].rstrip("%"))
                if r_low >= cur_high:
                    hike_prob += prob
                elif r_low < cur_low:
                    cut_prob += prob
                else:
                    hold_prob += prob

            row = {
                "meeting_date": meeting_date,
                "current_rate": current_target,
                "cut_prob": round(cut_prob, 1),
                "hold_prob": round(hold_prob, 1),
                "hike_prob": round(hike_prob, 1),
            }
            rows.append(row)

        df = pd.DataFrame(rows)
        if "meeting_date" in df.columns:
            df["date"] = pd.to_datetime(df["meeting_date"], errors="coerce")
        df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True) if "date" in df.columns else df

        logger.info(f"[fedwatch] 处理完成: {len(df)} 行")
        return df

    except ImportError:
        logger.warning("[fedwatch] cme-fedwatch 未安装，返回空")
        return pd.DataFrame()
    except Exception as e:
        logger.warning(f"[fedwatch] 获取失败: {e}")
        return pd.DataFrame()
