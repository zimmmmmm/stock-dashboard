# A股超短盯盘仪表盘

可视化仪表盘，零命令行操作。配 `ultra.py` 使用。

## 一键启动

```
双击 启动仪表盘.bat
```

浏览器自动打开，顶栏三个按钮完成所有操作：
- **拉行情** — 从腾讯/东财API拉最新数据
- **转记录** — 把交易日志转成结构化数据
- **同步** — git commit + push 推送到GitHub

## 换设备

```bash
git clone ssh://git@ssh.github.com:443/zimmmmmm/stock-dashboard.git
cd stock-dashboard
双击 启动仪表盘.bat
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

## 命令行（备用）

```bash
python scripts/export_data.py    # 拉行情
python scripts/convert_records.py # 转记录
python scripts/server.py         # 启动服务
```
