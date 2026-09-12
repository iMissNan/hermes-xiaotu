#!/usr/bin/env python3
"""8444 HTTP -> 8443 HTTPS 跳转器 — 让 Homarr 卡片能用纯 http href（与其它卡结构一致）."""
from http.server import BaseHTTPRequestHandler, HTTPServer

TARGET = os.environ.get("MONPANEL_DOMAIN_HTTPS", "https://<你的域名>:8443")


class H(BaseHTTPRequestHandler):
    def _r(self):
        self.send_response(301)
        self.send_header("Location", TARGET + self.path if self.path != "/" else TARGET + "/")
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_GET = do_POST = do_HEAD = _r

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8444), H).serve_forever()
