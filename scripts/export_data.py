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
# 自选池 — 从 watchlist.json 读取，仪表盘可编辑
# ============================================================
def load_watchlist():
    wl_path = os.path.join(DATA_DIR, 'watchlist.json')
    if os.path.exists(wl_path):
        with open(wl_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('stocks', {}), data.get('sectors', {})
    return {}, {}

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
os.makedirs(DATA_DIR, exist_ok=True)


def fetch_tencent(codes):
    """拉腾讯行情数据，自动添加交易所前缀"""
    # 添加交易所前缀: 60xxxx→sh, 00xxxx/002xxx→sz, s_→保持
    prefixed = []
    for c in codes:
        if c.startswith('s_'):
            prefixed.append(c)
        elif c.startswith('60') or c.startswith('68'):
            prefixed.append('sh' + c)
        else:
            prefixed.append('sz' + c)
    url = f"http://qt.gtimg.cn/q={','.join(prefixed)}"
    try:
        r = subprocess.run(['curl', '-s', '--connect-timeout', '5', '--max-time', '10', url],
                         capture_output=True, timeout=12)
        raw = r.stdout.decode('gbk', errors='replace')
        return raw
    except Exception as e:
        print(f"Tencent API failed: {e}")
        return ""


def fetch_limit_ups():
    """扫涨停板 — 腾讯API批量查询活跃股票池，筛出>=9.8%"""
    pool = _get_active_pool()
    all_stocks = []
    batch_size = 80
    for i in range(0, len(pool), batch_size):
        batch = pool[i:i+batch_size]
        raw = fetch_tencent(batch)
        quotes = parse_tencent(raw, is_index=False)
        for code, d in quotes.items():
            if d.get('pct', 0) >= 9.8:
                all_stocks.append({
                    'code': code, 'name': d['name'],
                    'price': d['price'], 'pct': d['pct'],
                    'turnover': d.get('turnover', 0),
                    'amount': d.get('amount', 0),
                })
    return all_stocks


def _get_active_pool():
    """活跃股票池：两市主板热门标的 + 自选池"""
    base = list(load_watchlist()[0].keys()) if os.path.exists(os.path.join(DATA_DIR, 'watchlist.json')) else []

    # 补充两市主板活跃标的（按行业分散覆盖）
    extra = [
        # 电力/能源
        '600900','600025','600011','600021','600027','600023','600886','600674',
        '600905','601778','600163','600483','600509','600578','600780','600795',
        '600863','600982','600116','000591','000537','000883','000027',
        # 电网设备
        '600406','600875','601179','601727','600550','600517','600312',
        # 半导体/电子
        '600460','600171','600703','600745','600360','603501','603160','603986',
        '002049','002185','002241','002268','002414','002436','002463',
        # AI/算力/软件
        '600536','600570','600588','600845','603019','603236','603383','603444',
        '002230','002261','002368','002371','002396','002415','002439',
        # 医药
        '600276','600196','600085','600436','600511','600535','600566','600587',
        '600763','600771','603259','603456','000538','000661','000963',
        # 消费
        '600519','600809','600887','600690','601888','603288','000858','002142',
        # 金融
        '601318','600036','601166','600030','601688','601066','000001','002142',
        # 有色/化工
        '600111','600392','600549','600988','601899','603799','000630','000831',
        '600309','600346','600426','600989','601117','603260','000830',
        # 军工
        '600118','600150','600316','600372','600391','600685','600760','600879',
        '000547','000733','000738','000768','002013','002025',
        # 汽车/新能源
        '600104','600418','600741','601238','601633','601689','000625','002594',
        # 建筑/地产
        '601668','601390','601800','600048','001979','000002',
        # 通信
        '600050','600105','600487','601869','000063',
        # 环保
        '600008','600323','601200','601330','000544','000598',
        # 农业
        '600598','601952','000876','002157','002311','002385','002505',
        # 周期/机械
        '600031','600150','600320','600583','601100','601608','000157',
    ]
    # 去重并添加交易所前缀
    for c in extra:
        if c not in base:
            base.append(c)
    return list(set(base))  # 去重


def fetch_market_breadth():
    """拉全市场涨跌家数（东财全市场概览）"""
    url = ("https://push2.eastmoney.com/api/qt/ulist.np/get?"
           "fltt=2&fields=f2,f3,f12,f104,f105,f106"
           "&secids=1.000001")
    try:
        r = subprocess.run(['curl', '-s', '--connect-timeout', '5', '--max-time', '10', url],
                         capture_output=True, timeout=12)
        data = json.loads(r.stdout.decode('utf-8'))
        info = {'up': 0, 'down': 0, 'limit_up': 0, 'limit_down': 0}
        if data.get('data') and data['data'].get('diff'):
            item = data['data']['diff'][0]
            info['up'] = item.get('f104', 0) or 0
            info['down'] = item.get('f105', 0) or 0
            info['limit_up'] = item.get('f106', 0) or 0
        return info
    except Exception:
        return {'up': 0, 'down': 0, 'limit_up': 0, 'limit_down': 0}


def fetch_sector_ranking():
    """拉行业板块涨跌排名 + 资金流向"""
    url = ("https://push2.eastmoney.com/api/qt/clist/get?"
           "fid=f3&po=1&pz=20&pn=1&np=1&fltt=2&invt=2"
           "&fields=f2,f3,f12,f14,f62,f184,f66"
           "&fs=m:90+t:2+f:!50")
    try:
        r = subprocess.run(['curl', '-s', '--connect-timeout', '5', '--max-time', '10', url],
                         capture_output=True, timeout=12)
        data = json.loads(r.stdout.decode('utf-8'))
        sectors = []
        if data.get('data') and data['data'].get('diff'):
            for item in data['data']['diff']:
                pct = item.get('f3', 0) or 0
                flow = item.get('f62', 0) or 0  # 主力净流入(元)
                flow_amount = round(flow / 1e8, 2)  # 转亿
                sectors.append({
                    'code': item.get('f12', ''),
                    'name': item.get('f14', ''),
                    'pct': pct,
                    'flow': flow_amount,  # 主力净流入(亿)
                })
        return sectors
    except Exception:
        return []


def fetch_concept_ranking():
    """拉概念板块涨跌排名 + 资金流向"""
    url = ("https://push2.eastmoney.com/api/qt/clist/get?"
           "fid=f3&po=1&pz=20&pn=1&np=1&fltt=2&invt=2"
           "&fields=f2,f3,f12,f14,f62"
           "&fs=m:90+t:3+f:!50")
    try:
        r = subprocess.run(['curl', '-s', '--connect-timeout', '5', '--max-time', '10', url],
                         capture_output=True, timeout=12)
        data = json.loads(r.stdout.decode('utf-8'))
        concepts = []
        if data.get('data') and data['data'].get('diff'):
            for item in data['data']['diff']:
                pct = item.get('f3', 0) or 0
                flow = item.get('f62', 0) or 0
                flow_amount = round(flow / 1e8, 2)
                concepts.append({
                    'code': item.get('f12', ''),
                    'name': item.get('f14', ''),
                    'pct': pct,
                    'flow': flow_amount,
                })
        return concepts
    except Exception:
        return []


def parse_tencent(raw, is_index=False):
    """解析腾讯API响应
    股票: parts[3]=现价, parts[4]=昨收, parts[5]=今开
    指数: parts[3]=现价, parts[4]=涨跌点(不是昨收!), parts[5]=今开
    """
    results = {}
    for line in raw.split('\n'):
        if '="' not in line:
            continue
        try:
            parts = line.split('~')
            name = parts[1]
            code = parts[2]
            price = float(parts[3]) if parts[3] else 0

            if is_index:
                # 指数: parts[4]是涨跌点，不是昨收
                point_change = float(parts[4]) if parts[4] else 0
                prev_close = price - point_change
                pct = round(point_change / prev_close * 100, 2) if prev_close else 0
                open_price = float(parts[5]) if parts[5] else 0
                results[code] = {
                    'code': code, 'name': name,
                    'price': price, 'prev_close': prev_close, 'pct': pct,
                    'open': open_price,
                    'high': 0, 'low': 0, 'turnover': 0, 'amount': 0,
                }
            else:
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
    """导出指数+自选池+全市场数据"""
    WATCHLIST, SECTOR_MAP = load_watchlist()
    if not WATCHLIST:
        print("Warning: watchlist.json 为空，请先初始化自选池")
        return

    # 拉指数（腾讯API对指数返回 价格/涨跌点，不是昨收）
    idx_raw = fetch_tencent(['s_sh000001', 's_sz399001', 's_sz399006', 's_sh000688'])
    idx_data = parse_tencent(idx_raw, is_index=True)

    indices = []
    # API返回的代码不带s_前缀，需要映射
    idx_code_map = {'000001': '上证指数', '399001': '深证成指',
                    '399006': '创业板指', '000688': '科创50'}
    for code, name in idx_code_map.items():
        d = idx_data.get(code, {})
        indices.append({
            'code': code, 'name': name,
            'price': d.get('price', 0), 'pct': round(d.get('pct', 0), 2),
            'status': 'up' if d.get('pct', 0) > 0 else ('down' if d.get('pct', 0) < 0 else 'flat'),
        })

    # 拉自选池
    codes = list(WATCHLIST.keys())
    raw = fetch_tencent(codes)
    quotes = parse_tencent(raw, is_index=False)

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

    # 拉全市场数据
    breadth = fetch_market_breadth()
    sectors = fetch_sector_ranking()
    concepts = fetch_concept_ranking()

    data = {
        'updated': datetime.now().isoformat(),
        'indices': indices,
        'watchlist': watchlist,
        # 全市场数据
        'market_breadth': breadth,
        'market_sectors': sectors,
        'market_concepts': concepts,
        # 自选池汇总
        'watchlist_summary': {
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
