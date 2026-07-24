#!/usr/bin/env python
"""
A股数据导出工具 — 复用ultra.py数据源，输出JSON供仪表盘使用
用法: python export_data.py          # 导出全部数据
      python export_data.py market   # 仅指数+自选
      python export_data.py zt       # 仅涨停板
"""

import subprocess, json, os, sys
from datetime import datetime

# ============================================================
# 自选池（与 ultra.py 同步维护）
# ============================================================
WATCHLIST = {
    '001258': '立新能源',   '600744': '华银电力',   '000767': '晋控电力',
    '002371': '北方华创',   '603986': '兆易创新',   '600584': '长电科技',
    '002156': '通富微电',   '603893': '瑞芯微',     '002409': '雅克科技',
    '000938': '紫光股份',   '002396': '星网锐捷',   '603118': '共进股份',
    '000063': '中兴通讯',   '002900': '哈三联',     '002793': '罗欣药业',
    '002197': '证通电子',   '000815': '美利云',     '002432': '九安医疗',
    '002213': '大为股份',   '603297': '永新光学',   '605111': '新洁能',
    '600406': '国电南瑞',   '600875': '东方电气',
}

# 板块分类（用于仪表盘分组）
SECTOR_MAP = {
    '001258': '电力', '600744': '电力', '000767': '电力',
    '600406': '电力', '600875': '电力',
    '002371': '半导体', '603986': '半导体', '600584': '半导体',
    '002156': '半导体', '603893': '半导体', '002409': '半导体',
    '000938': '交换机/AI', '002396': '交换机/AI', '603118': '交换机/AI',
    '000063': '交换机/AI', '002197': '算力', '000815': '算力',
    '002900': '医药', '002793': '医药', '002432': '医药',
    '002213': '半导体', '603297': '光学', '605111': '半导体',
}

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
os.makedirs(DATA_DIR, exist_ok=True)


def fetch_tencent(codes):
    """拉腾讯行情数据，处理GBK编码"""
    url = f"http://qt.gtimg.cn/q={','.join(codes)}"
    try:
        r = subprocess.run(['curl', '-s', '--connect-timeout', '5', '--max-time', '10', url],
                         capture_output=True, timeout=12)
        # Decode GBK with error tolerance, then re-encode to clean UTF-8
        raw = r.stdout.decode('gbk', errors='replace')
        return raw
    except Exception as e:
        print(f"Tencent API failed: {e}")
        return ""


def fetch_limit_ups():
    """拉东方财富涨停板数据"""
    url = ("https://push2.eastmoney.com/api/qt/clist/get?"
           "fid=f3&po=1&pz=200&pn=1&np=1&fltt=2&invt=2"
           "&fields=f2,f3,f4,f8,f12,f14,f15,f20"
           "&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048")
    try:
        r = subprocess.run(['curl', '-s', '--connect-timeout', '5', '--max-time', '10', url],
                         capture_output=True, timeout=12)
        data = json.loads(r.stdout.decode('utf-8'))
        stocks = []
        if data.get('data') and data['data'].get('diff'):
            for item in data['data']['diff']:
                pct = item.get('f3', 0)
                if pct and pct >= 9.8:
                    stocks.append({
                        'code': item.get('f12', ''),
                        'name': item.get('f14', ''),
                        'price': item.get('f2', 0),
                        'pct': pct,
                        'turnover': item.get('f8', 0),
                        'amount': round(item.get('f20', 0) / 1e8, 1) if item.get('f20') else 0,
                    })
        return stocks
    except Exception as e:
        print(f"东方财富API失败: {e}")
        return []


def parse_tencent(raw):
    """解析腾讯API响应"""
    results = {}
    for line in raw.split('\n'):
        if '="' not in line:
            continue
        try:
            parts = line.split('~')
            name = parts[1]
            code = parts[2]
            price = float(parts[3]) if parts[3] else 0
            prev_close = float(parts[4]) if parts[4] else 0
            pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0
            results[code] = {
                'code': code, 'name': name,
                'price': price, 'prev_close': prev_close, 'pct': pct,
                'open': float(parts[5]) if parts[5] else 0,
                'high': float(parts[33]) if len(parts) > 33 and parts[33] else 0,
                'low': float(parts[34]) if len(parts) > 34 and parts[34] else 0,
                'turnover': float(parts[38]) if len(parts) > 38 and parts[38] else 0,
                'amount': round(float(parts[37]) / 10000, 1) if len(parts) > 37 and parts[37] else 0,
            }
        except (ValueError, IndexError):
            continue
    return results


def get_status(pct, turnover=0):
    """根据涨跌幅判断状态"""
    if pct >= 9.8:
        return '涨停'
    elif pct >= 5:
        return '强势'
    elif pct > 0:
        return '飘红'
    elif pct > -3:
        return '弱势'
    else:
        return '下跌'


def export_market():
    """导出指数+自选池"""
    # 拉指数
    idx_raw = fetch_tencent(['s_sh000001', 's_sz399001', 's_sz399006', 's_sh000688'])
    idx_data = parse_tencent(idx_raw)

    indices = []
    idx_names = {'s_sh000001': '上证指数', 's_sz399001': '深证成指',
                 's_sz399006': '创业板指', 's_sh000688': '科创50'}
    for code, name in idx_names.items():
        d = idx_data.get(code, {})
        indices.append({
            'code': code, 'name': name,
            'price': d.get('price', 0), 'pct': d.get('pct', 0),
            'status': 'up' if d.get('pct', 0) > 0 else ('down' if d.get('pct', 0) < 0 else 'flat'),
        })

    # 拉自选池
    codes = list(WATCHLIST.keys())
    raw = fetch_tencent(codes)
    quotes = parse_tencent(raw)

    watchlist = []
    ups = downs = limit_ups = 0
    sector_stats = {}

    for code, name in WATCHLIST.items():
        d = quotes.get(code, {})
        pct = d.get('pct', 0)
        status = get_status(pct, d.get('turnover', 0))
        sector = SECTOR_MAP.get(code, '其他')

        if pct > 0:
            ups += 1
        elif pct < 0:
            downs += 1
        if status == '涨停':
            limit_ups += 1

        if sector not in sector_stats:
            sector_stats[sector] = {'count': 0, 'ups': 0, 'limit_ups': 0}
        sector_stats[sector]['count'] += 1
        if pct > 0:
            sector_stats[sector]['ups'] += 1
        if status == '涨停':
            sector_stats[sector]['limit_ups'] += 1

        watchlist.append({
            'code': code, 'name': name,
            'price': d.get('price', 0), 'prev_close': d.get('prev_close', 0),
            'pct': pct, 'turnover': d.get('turnover', 0),
            'amount': d.get('amount', 0),
            'open': d.get('open', 0), 'high': d.get('high', 0), 'low': d.get('low', 0),
            'status': status, 'sector': sector,
        })

    data = {
        'updated': datetime.now().isoformat(),
        'indices': indices,
        'watchlist': watchlist,
        'summary': {
            'total': len(watchlist), 'ups': ups, 'downs': downs,
            'flat': len(watchlist) - ups - downs, 'limit_ups': limit_ups,
            'sectors': sector_stats,
        },
    }

    path = os.path.join(DATA_DIR, 'market.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[OK] market.json ({len(watchlist)} stocks, up{ups}/down{downs}/limit-up{limit_ups})")
    return data


def export_limit_ups():
    """导出涨停板数据"""
    stocks = fetch_limit_ups()

    sector_count = {}
    for s in stocks:
        # 简单板块推断
        name = s['name']
        if any(kw in name for kw in ['电力', '能源', '电', '风', '光', '绿']):
            sec = '电力/能源'
        elif any(kw in name for kw in ['芯', '微', '半导', '存储', '封测']):
            sec = '半导体'
        elif any(kw in name for kw in ['药', '医', '生物']):
            sec = '医药'
        elif any(kw in name for kw in ['算', '数', '云', '网', '通信']):
            sec = '算力/通信'
        elif any(kw in name for kw in ['有色', '矿', '铝', '铜', '金', '银', '钢']):
            sec = '有色/资源'
        elif any(kw in name for kw in ['军工', '航', '兵', '防务']):
            sec = '军工'
        else:
            sec = '其他'
        sector_count[sec] = sector_count.get(sec, 0) + 1

    data = {
        'updated': datetime.now().isoformat(),
        'count': len(stocks),
        'stocks': stocks,
        'sector_distribution': sector_count,
    }

    path = os.path.join(DATA_DIR, 'limit-ups.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[OK] limit-ups.json ({len(stocks)} limit-ups)")
    return data


def export_all():
    export_market()
    export_limit_ups()
    print(f"\nDone -> {DATA_DIR}")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == 'market':
            export_market()
        elif sys.argv[1] == 'zt':
            export_limit_ups()
        else:
            export_all()
    else:
        export_all()
