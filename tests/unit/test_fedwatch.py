"""FedWatch 利率预期单元测试"""

from unittest.mock import patch

from gold_agent.data.fed_watch import fetch_fedwatch


def _mock_probabilities_all():
    """模拟 cme-fedwatch get_probabilities() 返回值 (dict with meetings list)"""
    return {
        "current_target": "4.25-4.50",
        "effr": "4.33",
        "meetings": [
            {
                "date": "2026-06-17",
                "contract": "ZNM6",
                "probabilities": {
                    "4.00-4.25": 65.0,
                    "4.25-4.50": 30.0,
                    "4.50-4.75": 5.0,
                },
            },
            {
                "date": "2026-07-29",
                "contract": "ZNQ6",
                "probabilities": {
                    "4.00-4.25": 55.0,
                    "4.25-4.50": 35.0,
                    "4.50-4.75": 10.0,
                },
            },
        ],
    }


class TestFetchFedwatch:
    """测试 FedWatch 数据获取"""

    def test_success(self):
        """正常获取概率数据"""
        with patch("cme_fedwatch.get_probabilities") as mock_gp:
            mock_gp.return_value = _mock_probabilities_all()

            result = fetch_fedwatch()

            assert not result.empty
            assert "meeting_date" in result.columns
            assert "cut_prob" in result.columns
            assert "hold_prob" in result.columns
            assert "hike_prob" in result.columns
            assert len(result) == 2

    def test_empty_data(self):
        """返回空列表时返回空 DataFrame"""
        with patch("cme_fedwatch.get_probabilities") as mock_gp:
            mock_gp.return_value = []

            result = fetch_fedwatch()

            assert result.empty

    def test_single_meeting_dict(self):
        """meetings 列表只有一个元素时也能处理"""
        mock_data = _mock_probabilities_all()
        mock_data["meetings"] = [mock_data["meetings"][0]]
        with patch("cme_fedwatch.get_probabilities") as mock_gp:
            mock_gp.return_value = mock_data

            result = fetch_fedwatch()

            assert not result.empty
            assert len(result) == 1

    def test_fetch_error(self):
        """API 异常时返回空 DataFrame"""
        with patch("cme_fedwatch.get_probabilities") as mock_gp:
            mock_gp.side_effect = Exception("API error")

            result = fetch_fedwatch()

            assert result.empty

    def test_meetings_as_dict(self):
        """meetings 字段为 dict 时转为 list（覆盖 line 30）"""
        mock_data = _mock_probabilities_all()
        # Set meetings to a single dict instead of list of dicts
        mock_data["meetings"] = mock_data["meetings"][0]
        with patch("cme_fedwatch.get_probabilities") as mock_gp:
            mock_gp.return_value = mock_data
            result = fetch_fedwatch()
            assert not result.empty
            assert len(result) == 1

    def test_rate_range_no_dash(self):
        """概率中的 rate_range 不含 '-' 时跳过（覆盖 line 43）"""
        mock_data = {
            "current_target": "4.25-4.50",
            "effr": "4.33",
            "meetings": [
                {
                    "date": "2026-06-17",
                    "contract": "ZNM6",
                    "probabilities": {
                        "4.25-4.50": 30.0,
                        "NO_DASH": 10.0,  # This should be skipped
                        "4.00-4.25": 60.0,
                    },
                },
            ],
        }
        with patch("cme_fedwatch.get_probabilities") as mock_gp:
            mock_gp.return_value = mock_data
            result = fetch_fedwatch()
            assert not result.empty
            assert len(result) == 1

    def test_import_error(self):
        """cme-fedwatch 未安装时返回空（覆盖 lines 71-72）"""
        import builtins
        import sys

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "cme_fedwatch":
                raise ImportError("No module named cme_fedwatch")
            return original_import(name, *args, **kwargs)

        orig_mod = sys.modules.pop("cme_fedwatch", None)
        try:
            with patch("builtins.__import__", side_effect=mock_import):
                from gold_agent.data.fed_watch import fetch_fedwatch as _fetch
                result = _fetch()
                assert result.empty
        finally:
            if orig_mod is not None:
                sys.modules["cme_fedwatch"] = orig_mod
