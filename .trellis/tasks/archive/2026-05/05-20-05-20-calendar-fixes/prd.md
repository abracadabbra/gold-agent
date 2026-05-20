# PRD: Calendrier + Correctifs + Réserves CB

## 动机
- 需要财务日历功能支持事件推送
- 多个线上数据源已失效（Kitco RSS、IMF SDMX API、FRED 金价系列）
- python 3.12 `datetime.utcnow()` 弃用警告需要处理

## 范围

### 功能
- 财务日历 mock 数据 + API 端点 `GET /api/analysis/calendar`
- 前端 CalendarCard 组件（突出下一大事件 + 列表）

### Bug 修复
- `TradeSignal` subscriptable → `signal.signal.value` (websocket.py)
- Kitco RSS 404 → `mining.com/feed` (news.py)
- Central bank `.dt` accessor → 显式 datetime 转换 (central_bank.py)
- `usd_cny` 无日期列 → 专用 fetch_china_fx 处理器 (china_macro.py)
- pandas `format='mixed'` 警告
- 删除死掉的 FRED `GOLDAMGBD228NLBM` (已从 FRED 移除)

### 重构
- Central bank reserves: 从 IMF SDMX API（已下线）切换到静态快照数据

### 测试
- 新增 central_bank + extra_data 测试（→ 10 个测试通过）
- China macro 测试 mock 更新

## 验收标准
- [x] `GET /api/analysis/calendar` 返回结构化日历数据
- [x] 前端 CalendarCard 渲染正常
- [x] 10 个新增测试通过
- [x] 所有已有测试通过（除预存失败）
- [x] ruff clean

## 不包含
- 真实经济日历 API 接入（需付费）
- 前端 WebSocket 客户端实现
