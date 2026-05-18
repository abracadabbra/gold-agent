# Quant 层测试

## Goal

为 `src/gold_agent/quant/` 模块补充单元测试：predictor, backtest engine。

## Modules to test

- `quant/predictor.py` — Prophet 时序预测
- `quant/backtest/engine.py` — backtrader 回测引擎

## Approach

- Mock Prophet 以避免实际训练（耗时 + 依赖）
- Mock backtrader 以避免 Cerebro 实际运行
- 测试数据类 BacktestResult 和格式化函数
- 验证异常分支（数据不足、未知策略）

## Acceptance Criteria

- [ ] predictor: mock Prophet，验证数据准备/回归因子/预测结果格式/异常
- [ ] backtest: mock backtrader，验证回测流程/结果提取/策略选择
- [ ] ruff check 通过
