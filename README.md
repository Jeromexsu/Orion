# Orion · 信息监控系统

设计文档：信息监控系统 · 核心骨架搭建指南

## 目录

```
src/
  core/<module>/     # target, collector, event, condition_engine, operators, hil, report
  plugins/<module>/  # 具体的 TargetType / Adapter / LeafConditionEvaluator / Operator 实现
  api/               # Web API 层（暂缓）
  persistence/       # 仓库实现 · ORM（暂缓）
  bootstrap.py       # 唯一的跨切面装配点
```

## 开发

```bash
uv sync
uv run pytest         # 测试
uv run pyright        # 类型检查（core 六个模块 strict）
uv run lint-imports   # 模块依赖边界
```
