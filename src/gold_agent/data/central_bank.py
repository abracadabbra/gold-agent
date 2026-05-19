"""央行黄金储备 — IMF IFS SDMX REST API"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

# IMF IFS API 基础 URL
IMF_BASE = "http://dataservices.imf.org/REST/SDMX_JSON.svc"

# 主要国家 IMF 代码
TOP_COUNTRIES = {
    "CN": "中国",
    "US": "美国",
    "RU": "俄罗斯",
    "IN": "印度",
    "JP": "日本",
    "CH": "瑞士",
    "DE": "德国",
    "IT": "意大利",
    "FR": "法国",
    "GB": "英国",
}


def fetch_central_bank_reserves(
    countries: list[str] | None = None,
    start_year: int = 2020,
) -> pd.DataFrame:
    """
    通过 IMF IFS API 获取各国央行黄金储备

    Args:
        countries: IMF 国家代码列表，默认 TOP10
        start_year: 起始年份

    Returns:
        DataFrame: country, date, gold_reserves_tonnes, gold_reserves_usd, rank
    """

    if countries is None:
        countries = list(TOP_COUNTRIES.keys())

    all_records = []

    for country in countries:
        try:
            records = _fetch_country_gold(country, start_year)
            if not records.empty:
                all_records.append(records)
                country_name = TOP_COUNTRIES.get(country, country)  # noqa: E501
                logger.info(f"[central_bank] {country_name}: {len(records)} 条")
            else:
                logger.warning(f"[central_bank] {country}: 无数据")
        except Exception as e:
            logger.warning(f"[central_bank] {country} 获取失败: {e}")

    if not all_records:
        logger.warning("[central_bank] 所有国家均获取失败")
        return pd.DataFrame()

    result = pd.concat(all_records, ignore_index=True)
    result = result.sort_values(["date", "country"]).reset_index(drop=True)

    # 添加排名（按最新黄金储备排序）
    latest = result.sort_values("date", ascending=False).drop_duplicates("country")
    latest["rank"] = latest["gold_reserves_tonnes"].rank(ascending=False, method="dense")
    rank_map = latest.set_index("country")["rank"].to_dict()
    result["rank"] = result["country"].map(rank_map)

    logger.info(f"[central_bank] 总计: {len(result)} 行, {result['country'].nunique()} 个国家")
    return result


def _fetch_country_gold(country: str, start_year: int = 2020) -> pd.DataFrame:
    """
    获取单个国家的黄金储备数据

    IMF IFS SDMX 查询格式:
        /CompactData/IFS/{FREQ}.{REF_AREA}.{INDICATOR}?startPeriod={year}

    IFS 黄金储备指标代码: FID (Monetary Authorities - Gold)
    """
    import json
    import urllib.request
    import urllib.error

    # 查询月度黄金储备 (FID = Foreign International Depository - Gold)
    # 也尝试 g1 和 FID_G
    indicators = ["FID", "FID_G", "G1"]

    for indicator in indicators:
        url = f"{IMF_BASE}/CompactData/IFS/M.{country}.{indicator}?startPeriod={start_year}"
        headers = {"User-Agent": "GoldAgent/1.0", "Accept": "application/json"}
        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
                data = json.loads(raw)
        except (urllib.error.HTTPError, urllib.error.URLError,
                json.JSONDecodeError, TimeoutError) as e:
            logger.debug(f"[central_bank] {country} indicator={indicator}: {e}")
            continue

        # 解析 SDMX JSON
        records = _parse_sdmx_compact(data)
        if not records.empty:
            records["country"] = country
            # 转换单位 (IMF 数据可能是百万美元或金衡盎司)
            # FID 通常以"百万美元"计价，需转换为吨
            # 1 金衡盎司 ≈ 31.1035 克
            # 1 吨 ≈ 32150.7 金衡盎司
            # 如果值很大可能是美元价值，如果值较小可能是吨或盎司
            if "value" in records.columns:
                records["gold_reserves_tonnes"] = _normalize_gold_value(records["value"])
                records["gold_reserves_usd"] = records.get("value", None)
                records = records.drop(columns=["value"], errors="ignore")
            return records

    logger.debug(f"[central_bank] {country}: 所有指标均失败")
    return pd.DataFrame()


def _parse_sdmx_compact(data: dict) -> pd.DataFrame:
    """解析 SDMX Compact Data JSON 为 DataFrame"""
    try:
        ds = data.get("CompactData", {}).get("DataSet", {})
        if not ds:
            return pd.DataFrame()

        series_list = ds.get("Series", [])
        if isinstance(series_list, dict):
            series_list = [series_list]

        rows = []
        for series in series_list:
            obs_list = series.get("Obs", [])
            if isinstance(obs_list, dict):
                obs_list = [obs_list]

            for obs in obs_list:
                obs_key = obs.get("@OBS_VALUE") or obs.get("OBS_VALUE", {}).get("$", "")
                time_key = obs.get("@TIME_PERIOD") or obs.get("TIME_PERIOD", {}).get("$", "")
                if obs_key and time_key:
                    rows.append({
                        "date": time_key,
                        "value": float(obs_key) if obs_key else None,
                    })

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)

        # 解析日期 (IMF 格式: YYYY, YYYY-MM, YYYY-Q1, etc.)
        def parse_imf_date(d):
            d = str(d)
            if len(d) == 4:  # 年度
                return pd.Timestamp(f"{d}-06-30")
            elif len(d) == 7:  # YYYY-MM
                return pd.Timestamp(f"{d}-01")
            elif "Q" in d.upper():
                parts = d.upper().split("Q")
                return pd.Timestamp(f"{parts[0]}-{int(parts[1])*3-2}-01")
            return pd.NaT

        df["date"] = df["date"].apply(parse_imf_date)
        df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

        logger.debug(f"[central_bank] 解析 SDMX: {len(df)} 行")
        return df

    except Exception as e:
        logger.debug(f"[central_bank] 解析 SDMX 失败: {e}")
        return pd.DataFrame()


def _normalize_gold_value(value_series: pd.Series) -> pd.Series:
    """
    将 IMF 黄金储备值归一化为吨

    IMF FID 数据通常以"百万美元"计，但不同国家可能有不同单位。
    我们根据数值量级做启发式推断:
      - > 1e9: 以美元计 → 需按金价除 (约 2000 美元/盎司)
      - < 1e6: 可能已是吨 → 直接返回
      - 之间: 可能是金衡盎司 → 转换为吨
    """

    def _convert(v):
        if pd.isna(v) or v == 0:
            return None
        if v > 1e8:
            # 百万美元估值 → 按当前金价折算为吨
            gold_price_per_oz = 2300  # 近似当前金价
            return v * 1e6 / gold_price_per_oz / 32150.7
        elif v > 1e5:
            # 金衡盎司 → 吨
            return v / 32150.7
        else:
            # 可能是吨
            return float(v)

    return value_series.apply(_convert)
