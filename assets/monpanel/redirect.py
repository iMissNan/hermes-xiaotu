#!/usr/bin/env python3
"""统一入口 HTTP redirector (port 80) — 按来源智能跳转到导航页."""
from http.server import BaseHTTPRequestHandler, HTTPServer

LAN_IP = os.environ.get("MONPANEL_LAN_IP", "<内网IP>")
TS_IP = os.environ.get("MONPANEL_TS_IP", "<Tailscale IP>")
DOMAIN = os.environ.get("MONPANEL_DOMAIN", "<你的域名>")  # 支持域名 Host 头
DASH_PORT = 7575


class RedirectHandler(BaseHTTPRequestHandler):
    def _redirect(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        if host == TS_IP:
            target = f"http://{TS_IP}:{DASH_PORT}/"
        elif host == DOMAIN:
            # 域名访问 → 跳域名：Tailscale 用户能走子网路由，本地用户走内网直连
            target = f"http://{DOMAIN}:{DASH_PORT}/"
        else:
            target = f"http://{LAN_IP}:{DASH_PORT}/"
        self.send_response(302)
        self.send_header("Location", target)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        self._redirect()

    def do_POST(self):
        self._redirect()

    def do_HEAD(self):
        self._redirect()

    def log_message(self, fmt, *args):
        pass  # keep redirector silent


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 80), RedirectHandler).serve_forever()
