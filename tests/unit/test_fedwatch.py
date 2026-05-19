"""FedWatch 利率预期单元测试"""

from unittest.mock import patch

from gold_agent.data.fed_watch import fetch_fedwatch


def _mock_probabilities_all():
    """模拟 cme-fedwatch get_probabilities('all') 返回值"""
    return [
        {
            "meetingDate": "2026-06-17",
            "currentRate": 4.50,
            "probabilities": {
                "cut": 65.0,
                "hold": 30.0,
                "hike": 5.0,
            },
        },
        {
            "meetingDate": "2026-07-29",
            "currentRate": 4.50,
            "probabilities": {
                "cut": 55.0,
                "hold": 35.0,
                "hike": 10.0,
            },
        },
    ]


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

    def test_single_dict(self):
        """返回单个 dict 而非 list 时也能处理"""
        mock_data = _mock_probabilities_all()[0]
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
