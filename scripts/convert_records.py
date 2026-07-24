#!/usr/bin/env python
"""
交易记录转换工具 — 将Markdown交易日志转为结构化JSON
用法: python convert_records.py
"""

import os, re, json
from datetime import datetime

RECORDS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'records')
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')


def parse_record(filepath):
    """解析单个交易日志文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 提取日期
    date_match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', content)
    if not date_match:
        return None
    date_str = f"{date_match.group(1)}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}"

    # 提取星期
    week_match = re.search(r'[周][一二三四五六日]', content)
    day_of_week = week_match.group(0) if week_match else ''

    entry = {
        'date': date_str,
        'day_of_week': day_of_week,
        'source_file': os.path.basename(filepath),
    }

    # 提取指数收盘
    idx_patterns = {
        'shanghai': r'上证.*?(\d+\.?\d*).*?([+-]?\d+\.?\d*)%',
        'shenzhen': r'深证.*?(\d+\.?\d*).*?([+-]?\d+\.?\d*)%',
        'chuangyeban': r'创业板.*?(\d+\.?\d*).*?([+-]?\d+\.?\d*)%',
        'kechuang50': r'科创.*?(\d+\.?\d*).*?([+-]?\d+\.?\d*)%',
    }
    market_close = {}
    for key, pat in idx_patterns.items():
        m = re.search(pat, content)
        if m:
            market_close[key] = {'price': float(m.group(1)), 'pct': float(m.group(2))}

    # 提取涨跌比
    breadth_match = re.search(r'(\d+)\s*涨.*?(\d+)\s*跌', content)
    up_count = int(breadth_match.group(1)) if breadth_match else 0
    down_count = int(breadth_match.group(2)) if breadth_match else 0

    # 提取涨停数
    zt_match = re.search(r'涨停[≈\s]*(\d+)', content)
    limit_up_count = int(zt_match.group(1)) if zt_match else 0
    dt_match = re.search(r'跌停[≈\s]*(\d+)', content)
    limit_down_count = int(dt_match.group(1)) if dt_match else 0

    market_close['breadth'] = {
        'up': up_count, 'down': down_count,
        'limit_up': limit_up_count, 'limit_down': limit_down_count,
    }
    entry['market_close'] = market_close

    # 提取连板梯队
    lianban = []
    board_pattern = re.findall(r'(\d+)板.*?[┃|].*?(\w+)\((\d{6})\)', content)
    board_levels = {}
    for level, name, code in board_pattern:
        level = int(level)
        if level not in board_levels:
            board_levels[level] = []
        board_levels[level].append({'name': name, 'code': code})

    for level in sorted(board_levels.keys(), reverse=True):
        lianban.append({'level': level, 'stocks': board_levels[level]})
    entry['lianban'] = lianban

    # 提取板块强度表
    sectors = []
    sector_rows = re.findall(
        r'\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(🔥+)\s*\|\s*(\d+)\+\s*\|\s*(.+?)\s*\|',
        content
    )
    for rank, name, heat, count, phase in sector_rows:
        sectors.append({
            'rank': int(rank), 'name': name.strip(),
            'heat': heat.strip(), 'limit_up_count': int(count),
            'phase': phase.strip(),
        })
    entry['sectors'] = sectors

    # 提取交易操作
    trades = []
    trade_pattern = re.findall(
        r'\|\s*(.+?)\((\d{6})\)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|',
        content
    )
    for name, code, action, cost, status in trade_pattern:
        trades.append({
            'name': name.strip(), 'code': code.strip(),
            'action': action.strip(), 'cost': cost.strip(),
            'status': status.strip(),
        })
    entry['trades'] = trades

    return entry


def convert_all():
    """扫描并转换所有交易记录"""
    if not os.path.exists(RECORDS_DIR):
        print(f"记录目录不存在: {RECORDS_DIR}")
        return

    entries = []
    for fname in sorted(os.listdir(RECORDS_DIR)):
        if fname.endswith('交易日志.md'):
            fpath = os.path.join(RECORDS_DIR, fname)
            entry = parse_record(fpath)
            if entry:
                entries.append(entry)
                print(f"[OK] {fname}")

    data = {'updated': datetime.now().isoformat(), 'entries': entries}
    path = os.path.join(DATA_DIR, 'journal.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\nDone -> journal.json ({len(entries)} entries)")


if __name__ == '__main__':
    convert_all()
