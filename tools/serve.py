#!/usr/bin/env python3
"""Serve site/ locally and print a phone-friendly LAN URL.

Usage:
    python tools/serve.py
    python tools/serve.py --port 8787 --local-only
    python tools/serve.py --no-open
"""
from __future__ import annotations

import argparse
import functools
import http.server
import socket
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "site"


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".js": "application/javascript; charset=utf-8",
        ".mjs": "application/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".webmanifest": "application/manifest+json; charset=utf-8",
        ".svg": "image/svg+xml",
        ".woff2": "font/woff2",
    }

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def log_message(self, fmt, *args):  # noqa: A003
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def lan_ips() -> list[str]:
    ips: set[str] = set()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.25)
        sock.connect(("8.8.8.8", 80))
        ips.add(sock.getsockname()[0])
        sock.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass
    return sorted(ips)


def main() -> int:
    parser = argparse.ArgumentParser(description="二合情报站本地服务")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--dir", default=str(DEFAULT_DIR))
    parser.add_argument("--local-only", action="store_true", help="只监听 127.0.0.1")
    parser.add_argument("--no-open", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()

    site_dir = Path(args.dir)
    if not (site_dir / "index.html").exists():
        print(f"找不到 {site_dir / 'index.html'}，请先在项目根目录运行 python tools/build.py")
        return 1

    bind = "127.0.0.1" if args.local_only else "0.0.0.0"
    handler = functools.partial(Handler, directory=str(site_dir))
    httpd = None
    port = args.port
    for candidate in range(args.port, args.port + 20):
        try:
            httpd = http.server.ThreadingHTTPServer((bind, candidate), handler)
            port = candidate
            break
        except OSError:
            continue
    if httpd is None:
        print(f"端口 {args.port}–{args.port + 19} 都被占用，请用 --port 换一个。")
        return 1

    local_url = f"http://127.0.0.1:{port}/"
    print("二合情报站已启动")
    print(f"  本机：{local_url}")
    if not args.local_only:
        for ip in lan_ips():
            print(f"  手机：http://{ip}:{port}/   （需同一 Wi-Fi，首次可能要允许 Windows 防火墙）")
    print("  Ctrl+C 停止")
    if not args.no_open:
        threading.Timer(0.6, lambda: webbrowser.open(local_url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
