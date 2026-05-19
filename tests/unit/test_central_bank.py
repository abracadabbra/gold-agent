"""央行黄金储备数据采集单元测试"""

import json
from unittest.mock import MagicMock, patch

from gold_agent.data.central_bank import (
    fetch_central_bank_reserves,
)


def _make_mock_response(data: dict):
    """创建模拟 urlopen 响应"""
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(data).encode("utf-8")
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_resp
    mock_cm.__exit__.return_value = None
    return mock_cm


def _sdmx_gold_data():
    """模拟 IMF SDMX 黄金储备响应"""
    return {
        "CompactData": {
            "DataSet": {
                "Series": [
                    {
                        "@REF_AREA": "CN",
                        "@INDICATOR": "FID",
                        "Obs": [
                            {"@TIME_PERIOD": "2024-01", "@OBS_VALUE": "60000"},
                            {"@TIME_PERIOD": "2024-02", "@OBS_VALUE": "61000"},
                        ],
                    }
                ]
            }
        }
    }


class TestFetchCentralBank:
    """测试央行黄金储备获取"""

    def test_success(self):
        """正常获取央行数据"""
        mock_resp = _make_mock_response(_sdmx_gold_data())
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = fetch_central_bank_reserves(countries=["CN"])

            assert not result.empty
            assert "country" in result.columns
            assert "date" in result.columns
            assert "gold_reserves_tonnes" in result.columns
            assert "gold_reserves_usd" in result.columns
            assert "rank" in result.columns

    def test_multiple_countries(self):
        """多国数据合并返回"""
        cn_data = _sdmx_gold_data()
        us_data = {
            "CompactData": {
                "DataSet": {
                    "Series": [
                        {
                            "@REF_AREA": "US",
                            "@INDICATOR": "FID",
                            "Obs": [
                                {"@TIME_PERIOD": "2024-01", "@OBS_VALUE": "80000"},
                            ],
                        }
                    ]
                }
            }
        }

        call_count = [0]

        def mock_urlopen(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return _make_mock_response(cn_data)
            return _make_mock_response(us_data)

        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            result = fetch_central_bank_reserves(countries=["CN", "US"])

            assert not result.empty
            assert result["country"].nunique() == 2

    def test_all_countries_fail(self):
        """所有国家都获取失败时返回空"""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = Exception("IMF API unavailable")

            result = fetch_central_bank_reserves(countries=["CN", "US"])

            assert result.empty

    def test_partial_failure(self):
        """部分国家失败不影响其他"""
        call_count = [0]

        def mock_urlopen(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return _make_mock_response(_sdmx_gold_data())
            raise Exception("Second country fails")

        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            result = fetch_central_bank_reserves(countries=["CN", "US"])

            assert not result.empty
            assert "CN" in result["country"].values
            assert "US" not in result["country"].values
