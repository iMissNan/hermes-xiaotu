#!/usr/bin/env python3
"""
AO 阶段汇报面板（:20133）— 只读 hermes-handover sidecar 库（handover.db）
2026-09-11 方案 A 落地件：AO 举手汇报的网页出口（大盘 20132 的姊妹页）。
安全设计：sqlite 只读模式打开（防面板写库）+ 全内容 html.escape（防汇报正文注入）+
纯内联样式零外链（复刻场景常遇外部 CDN 不可达，同源交付最稳）。浅色网格风。
"""
import sqlite3, json, html, os, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

DB_PATH = os.environ.get('AO_HANDOVER_DB', os.path.expanduser('~/.hermes/handover.db'))

CSS = """
body{font-family:system-ui,'PingFang SC','Microsoft YaHei',sans-serif;margin:0;background:#f5f7fa;color:#1a202c}
.wrap{max-width:960px;margin:0 auto;padding:24px 16px}
h1{font-size:20px;margin:0 0 4px}
.sub{color:#718096;font-size:13px;margin-bottom:20px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.card{background:#fff;border-radius:10px;padding:14px 16px;box-shadow:0 1px 3px rgba(0,0,0,.06);border:1px solid #e2e8f0}
.card:hover{border-color:#a0aec0}
.sess{font-family:monospace;font-size:13px;font-weight:600}
.meta{color:#718096;font-size:12px;margin-top:6px}
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px;font-weight:600}
.ok{background:#c6f6d5;color:#22543d}.skip{background:#e2e8f0;color:#4a5568}
.err{background:#fed7d7;color:#742a2a}.warn{background:#feebc8;color:#744210}
a{color:#2b6cb0;text-decoration:none}a:hover{text-decoration:underline}
.msg{background:#fff;border-radius:10px;border:1px solid #e2e8f0;padding:16px;margin-bottom:14px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
.msg pre{white-space:pre-wrap;word-break:break-word;font-family:inherit;font-size:14px;line-height:1.6;margin:0}
.top{display:flex;gap:10px;align-items:center;margin-bottom:14px;flex-wrap:wrap}
.btn{background:#2b6cb0;color:#fff;padding:6px 14px;border-radius:8px;font-size:13px}
.empty{color:#718096;text-align:center;padding:60px 0;font-size:14px}
"""

def badge_class(status):
    return {'completed': 'ok', 'skipped': 'skip', 'error': 'err', 'failed': 'err'}.get(status or '', 'warn')

def get_db():
    con = sqlite3.connect(f'file:{DB_PATH}?mode=ro', uri=True, timeout=5)
    con.row_factory = sqlite3.Row
    return con

def page_sessions():
    try:
        con = get_db()
        rows = con.execute('''SELECT session_id, COUNT(*) n, MAX(created_at) last,
            SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) ok
            FROM handover_messages GROUP BY session_id ORDER BY last DESC''').fetchall()
        con.close()
    except sqlite3.OperationalError:
        rows = []
    cards = ''.join(
        f'<a class="card" href="/?session={html.escape(r["session_id"])}"><span class="sess">{html.escape(r["session_id"])}</span>'
        f'<div class="meta">{r["n"]} 条汇报 · ✅ {r["ok"] or 0} 条通过 · 最近 {time.strftime("%m-%d %H:%M", time.localtime(r["last"]))}</div></a>'
        for r in rows) or '<div class="empty">暂无汇报——AO 工作流跑起来后，专家举手会出现在这里</div>'
    return f'<!doctype html><html><head><meta charset="utf-8"><title>AO 阶段汇报面板</title><style>{CSS}</style></head><body><div class="wrap"><h1>📋 AO 阶段汇报面板</h1><div class="sub">只读 sidecar（handover.db）· 引擎举手自动推送 · 详细产出见 <a href="http://{HOST}:20132/">运行大盘 20132</a></div><div class="grid">{cards}</div></div></body></html>'

def page_session(sid):
    try:
        con = get_db()
        rows = con.execute('SELECT * FROM handover_messages WHERE session_id=? ORDER BY id DESC', (sid,)).fetchall()
        con.close()
    except sqlite3.OperationalError:
        rows = []
    msgs = ''.join(
        f'<div class="msg"><pre>{html.escape(r["content"])}</pre>'
        f'<div class="meta" style="margin-top:10px">落库时间 {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["created_at"]))}</div></div>'
        for r in rows) or '<div class="empty">该会话暂无汇报记录</div>'
    return f'<!doctype html><html><head><meta charset="utf-8"><title>汇报 · {html.escape(sid)}</title><style>{CSS}</style></head><body><div class="wrap"><div class="top"><a class="btn" href="/">← 返回列表</a><h1 style="margin:0">{html.escape(sid)}</h1></div>{msgs}</div></body></html>'

def api_json(qs):
    try:
        con = get_db()
        if 'session' in qs:
            rows = [dict(r) for r in con.execute(
                'SELECT id, session_id, role, step_id, status, content, created_at FROM handover_messages WHERE session_id=? ORDER BY id DESC',
                (qs['session'][0],))]
        else:
            rows = [dict(r) for r in con.execute(
                'SELECT session_id, COUNT(*) n, MAX(created_at) last FROM handover_messages GROUP BY session_id ORDER BY last DESC')]
        con.close()
        return json.dumps({'ok': True, 'data': rows}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({'ok': False, 'error': str(e)}, ensure_ascii=False)

HOST = os.environ.get('AO_BOARD_HOST', '0.0.0.0')  # 监听地址；对外展示链接前缀另用 AO_BOARD_URL 环境变量

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        if u.path == '/api':
            body, ct = api_json(qs), 'application/json; charset=utf-8'
        elif u.path == '/' and 'session' in qs:
            body, ct = page_session(qs['session'][0]), 'text/html; charset=utf-8'
        elif u.path == '/healthz':
            body, ct = '{"ok":true}', 'application/json'
        else:
            body, ct = page_sessions(), 'text/html; charset=utf-8'
        data = body.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', ct)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass

if __name__ == '__main__':
    port = int(os.environ.get('AO_BOARD_PORT', '20133'))
    ThreadingHTTPServer(('0.0.0.0', port), Handler).serve_forever()
