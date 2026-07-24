# A股超短盯盘仪表盘

纯HTML单文件可视化仪表盘，配合 `ultra.py` 使用。双击即开，零依赖。

## 快速开始

```bash
# 1. 导出数据
python scripts/export_data.py

# 2. 转换交易记录
python scripts/convert_records.py

# 3. 打开仪表盘
# 双击 index.html 或浏览器打开
```

## 跨设备同步（GitHub）

```bash
# 首次
git init && git add . && git commit -m "init" && git push

# 每次换设备
git pull
python scripts/export_data.py
python scripts/convert_records.py
# 打开 index.html

# 每次更新后同步
git add data/ && git commit -m "update" && git push
```

## 7个Tab

| Tab | 内容 |
|:--|:--|
| 大盘 | 四大指数+涨跌分布+板块概览 |
| 自选 | 23只自选股表格（可排序/筛选） |
| 涨停板 | 涨停家数+涨停列表+板块分布 |
| 持仓 | 持仓表+P&L+手动编辑 |
| 板块强度 | 板块排名+连板梯队金字塔 |
| 交易记录 | 按日期导航的复盘数据 |
| 策略库 | 6个超短策略框架卡片 |

## 数据文件

- `data/market.json` — 指数+自选池实时快照
- `data/limit-ups.json` — 涨停板列表
- `data/positions.json` — 持仓（手动维护）
- `data/journal.json` — 结构化交易日志
- `data/strategies.json` — 策略框架

## 实时模式（可选）

```bash
# 启动本地HTTP服务实现30秒自动刷新
python -m http.server 8765
# 打开 http://localhost:8765
```
