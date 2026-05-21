# 行情数据展示优化 — 执行计划

## 执行顺序

由于 2 和 3 在代码层面不依赖 1，3 个孩子可以并行实施。
建议顺序：Child 1 → Child 2 → Child 3（先核心功能，再体验，最后布局）。

## 验证命令

每个子任务实施后都需要验证：

```bash
# Lint
cd frontend && npx next lint

# Typecheck
cd frontend && npx tsc --noEmit

# 检查是否新增了不必要的依赖（如果引入 lightweight-charts）
```

## 回滚点

- 每个子任务完成后 `git commit`，便于单独回滚
- 如果 lightweight-charts 方案有问题，可回退到 Recharts 自定义 K 线
