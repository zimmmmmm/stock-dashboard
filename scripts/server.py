#!/usr/bin/env python
"""
A股仪表盘本地服务器 — 提供数据刷新、转换、同步的API
用法: python server.py
然后浏览器打开 http://localhost:8765
"""
import http.server
import subprocess
import json
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / 'scripts'
DATA = ROOT / 'data'

class DashboardServer(http.server.SimpleHTTPRequestHandler):
    """静态文件 + API端点"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        if self.path == '/api/health':
            return self.json_resp({'ok': True, 'time': time.strftime('%H:%M:%S')})

        if self.path == '/api/export':
            return self.run_script('export_data.py', '拉取行情数据')

        if self.path == '/api/convert':
            return self.run_script('convert_records.py', '转换交易记录')

        if self.path == '/api/git-push':
            return self.git_push()

        if self.path == '/api/status':
            return self.get_status()

        if self.path.startswith('/api/search'):
            return self.search_stock()

        if self.path == '/api/watchlist':
            return self.get_watchlist()

        if self.path.startswith('/api/watchlist/save'):
            return self.save_watchlist()

        # Serve static files
        return super().do_GET()

    def run_script(self, script_name, label):
        """运行Python脚本并返回结果"""
        try:
            r = subprocess.run(
                [sys.executable, str(SCRIPTS / script_name)],
                capture_output=True, timeout=30,
                cwd=str(ROOT)
            )
            output = r.stdout.decode('gbk', errors='replace')
            if r.returncode != 0:
                output += '\n' + r.stderr.decode('gbk', errors='replace')
            success = r.returncode == 0
            return self.json_resp({
                'ok': success,
                'action': label,
                'output': output.strip(),
            })
        except Exception as e:
            return self.json_resp({'ok': False, 'action': label, 'output': str(e)})

    def git_push(self):
        """执行 git add + commit + push"""
        try:
            # git add
            subprocess.run(['git', 'add', str(DATA)], capture_output=True, timeout=10, cwd=str(ROOT))
            # git commit
            msg = f"auto: {time.strftime('%Y-%m-%d %H:%M')}"
            subprocess.run(['git', 'commit', '-m', msg], capture_output=True, timeout=10, cwd=str(ROOT))
            # git push
            r = subprocess.run(['git', 'push'], capture_output=True, timeout=30, cwd=str(ROOT))
            output = r.stdout.decode('utf-8', errors='replace')
            if r.returncode != 0:
                output += '\n' + r.stderr.decode('utf-8', errors='replace')
            return self.json_resp({
                'ok': r.returncode == 0,
                'action': 'Git同步',
                'output': output.strip() or '已同步',
            })
        except Exception as e:
            return self.json_resp({'ok': False, 'action': 'Git同步', 'output': str(e)})

    def get_status(self):
        """返回数据文件状态"""
        status = {}
        for f in ['market.json', 'limit-ups.json', 'journal.json', 'positions.json']:
            p = DATA / f
            if p.exists():
                mtime = time.strftime('%H:%M:%S', time.localtime(p.stat().st_mtime))
                size = round(p.stat().st_size / 1024, 1)
                status[f] = {'updated': mtime, 'size_kb': size}
            else:
                status[f] = {'updated': '--', 'size_kb': 0}
        return self.json_resp(status)

    def do_POST(self):
        if self.path == '/api/watchlist/save':
            return self.save_watchlist()
        self.send_response(404)
        self.end_headers()

    def search_stock(self):
        """搜索股票，支持代码或名称"""
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(self.path).query)
        keyword = qs.get('q', [''])[0]
        if not keyword:
            return self.json_resp([])

        # 东方财富搜索API
        url = (f"https://searchadapter.eastmoney.com/api/suggest/get?"
               f"input={keyword}&type=14&token=D43BF722C8E33BDC906FB84D85E326E8&count=10")
        try:
            r = subprocess.run(['curl', '-s', '--connect-timeout', '5', '--max-time', '10', url],
                             capture_output=True, timeout=12)
            data = json.loads(r.stdout.decode('utf-8'))
            results = []
            if data.get('QuotationCodeTable') and data['QuotationCodeTable'].get('Data'):
                for item in data['QuotationCodeTable']['Data']:
                    code = item.get('Code', '')
                    name = item.get('Name', '')
                    mkt = item.get('MktNum', '')
                    # 只保留A股主板（沪市1, 深市0）
                    if code and name and mkt in ('0', '1'):
                        # 过滤掉300/688开头的创业板科创板
                        if not code.startswith('300') and not code.startswith('688'):
                            results.append({'code': code, 'name': name, 'market': '沪' if mkt=='1' else '深'})
            return self.json_resp(results[:8])
        except Exception:
            return self.json_resp([])

    def get_watchlist(self):
        wl_path = DATA / 'watchlist.json'
        if wl_path.exists():
            with open(wl_path, 'r', encoding='utf-8') as f:
                return self.json_resp(json.load(f))
        return self.json_resp({'stocks': {}, 'sectors': {}})

    def save_watchlist(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            data = json.loads(body)
            with open(DATA / 'watchlist.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return self.json_resp({'ok': True, 'count': len(data.get('stocks', {}))})
        except Exception as e:
            return self.json_resp({'ok': False, 'error': str(e)})

    def json_resp(self, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # 静默日志


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = http.server.HTTPServer(('0.0.0.0', port), DashboardServer)
    print(f'仪表盘服务已启动 -> http://localhost:{port}')
    print('按 Ctrl+C 停止')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止')


if __name__ == '__main__':
    main()
