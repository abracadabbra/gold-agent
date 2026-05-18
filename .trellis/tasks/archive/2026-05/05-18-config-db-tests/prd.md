# Config + DB 测试

## Goal

为 config.py 和 db/models.py 补充单元测试。

## Approach

- Config: 测试 pydantic-settings 加载和目录创建
- DB: 测试模型实例化和辅助函数（无需真实数据库）

## Acceptance Criteria

- [ ] config: Settings 默认值/ensure_dirs 目录创建
- [ ] db: 9 个模型实例化/__repr__/create_tables/get_table_stats
- [ ] ruff check 通过
