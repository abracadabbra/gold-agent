"""JSON 序列化工具单元测试"""

import pandas as pd

from gold_agent.utils.json import json_safe


class TestJsonSafe:
    """测试 json_safe 函数"""

    def test_empty_df_returns_empty_list(self):
        result = json_safe(pd.DataFrame())
        assert result == []

    def test_normal_data_converts_to_records(self):
        df = pd.DataFrame({"a": [1, 2], "b": [3.0, 4.5]})
        result = json_safe(df)
        assert result == [{"a": 1, "b": 3.0}, {"a": 2, "b": 4.5}]

    def test_nan_values_become_none(self):
        import numpy as np
        df = pd.DataFrame({"a": [1.0, np.nan], "b": [np.nan, "text"]})
        result = json_safe(df)
        assert result == [{"a": 1.0, "b": None}, {"a": None, "b": "text"}]

    def test_nat_values_become_none(self):
        df = pd.DataFrame({
            "date": pd.to_datetime(["2024-01-01", None, "2024-01-03"]),
        })
        result = json_safe(df)
        assert result[0]["date"] is not None
        assert result[1]["date"] is None
        assert result[2]["date"] is not None

    def test_mixed_types(self):
        import numpy as np
        df = pd.DataFrame({
            "int_col": [1, 2, 3],
            "float_col": [1.1, 2.2, np.nan],
            "str_col": ["a", None, "c"],
        })
        result = json_safe(df)
        assert result[2]["float_col"] is None
        assert result[1]["str_col"] is None
        assert result[0]["str_col"] == "a"

    def test_inf_values_become_none(self):
        import numpy as np
        df = pd.DataFrame({"x": [np.inf, 1.0, -np.inf]})
        result = json_safe(df)
        assert result[0]["x"] is None
        assert result[1]["x"] == 1.0
        assert result[2]["x"] is None
