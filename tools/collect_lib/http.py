"""统一 HTTP 客户端（Python 标准库）。

要求（docs/COLLECTOR_BRIEF.md 第 3、8 节）：
- 统一 UA、超时、重试（403/429/5xx 退避 2 次）、请求间隔 ≥0.35s；
- config.proxy 非空时走 ProxyHandler；
- 失败抛 FetchError，由调用方隔离单个源，不影响其他源。

测试时不联网：只需构造 HttpClient(interval=0, retries=0) 即可。
"""
from __future__ import annotations

import gzip
import json
import socket
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Mapping, Optional

DEFAULT_USER_AGENT = "Merge2Radar/1.0 (personal research; contact: local)"
RETRYABLE_STATUS = {403, 408, 425, 429, 500, 502, 503, 504}


class FetchError(Exception):
    """一次请求在重试耗尽后仍然失败。"""

    def __init__(self, url: str, reason: Any):
        self.url = url
        self.reason = reason
        super().__init__(f"GET 失败：{url}（{reason}）")


class HttpClient:
    """带限速与重试的极简 HTTP 客户端。"""

    def __init__(
        self,
        timeout: float = 20.0,
        retries: int = 2,
        user_agent: str = DEFAULT_USER_AGENT,
        interval: float = 0.35,
        proxy: str = "",
        logger: Optional[Callable[[str], None]] = None,
        sleep: Callable[[float], None] = time.sleep,
        backoff: float = 0.8,
        max_backoff: float = 5.0,
    ) -> None:
        self.timeout = float(timeout)
        self.retries = max(0, int(retries))
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self.interval = max(0.0, float(interval))
        self.proxy = (proxy or "").strip()
        self.log = logger or (lambda _message: None)
        self._sleep = sleep
        self._backoff = backoff
        self._max_backoff = max_backoff
        self._last_request = 0.0
        handlers = []
        if self.proxy:
            handlers.append(urllib.request.ProxyHandler({"http": self.proxy, "https": self.proxy}))
        self._opener = urllib.request.build_opener(*handlers)

    # -- 内部工具 ---------------------------------------------------------
    def _throttle(self) -> None:
        if self.interval <= 0:
            return
        wait = self._last_request + self.interval - time.monotonic()
        if wait > 0:
            self._sleep(wait)
        self._last_request = time.monotonic()

    def _sleep_backoff(self, attempt: int) -> None:
        delay = min(self._max_backoff, self._backoff * (2 ** attempt))
        self.log(f"  重试第 {attempt + 1} 次，{delay:.1f}s 后继续")
        self._sleep(delay)

    def _open_once(self, url: str, headers: Mapping[str, str]) -> bytes:
        request_headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/xml, application/xml, */*",
        }
        request_headers.update(headers)
        request = urllib.request.Request(url, headers=request_headers)
        with self._opener.open(request, timeout=self.timeout) as response:
            data = response.read()
            if response.headers.get("Content-Encoding", "").lower() == "gzip":
                data = gzip.decompress(data)
            return data

    # -- 公开 API ---------------------------------------------------------
    def get_bytes(self, url: str, headers: Optional[Mapping[str, str]] = None) -> bytes:
        """GET 字节；失败重试后抛 FetchError。"""
        attempts = self.retries + 1
        last_error: Any = None
        for attempt in range(attempts):
            self._throttle()
            try:
                return self._open_once(url, headers or {})
            except urllib.error.HTTPError as exc:
                last_error = f"HTTP {exc.code}"
                if exc.code not in RETRYABLE_STATUS or attempt >= attempts - 1:
                    break
                self._sleep_backoff(attempt)
            except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as exc:
                last_error = exc
                if attempt >= attempts - 1:
                    break
                self._sleep_backoff(attempt)
        raise FetchError(url, last_error)

    def get_text(self, url: str, headers: Optional[Mapping[str, str]] = None) -> str:
        return self.get_bytes(url, headers=headers).decode("utf-8", errors="replace")

    def get_json(self, url: str, headers: Optional[Mapping[str, str]] = None) -> Any:
        text = self.get_text(url, headers=headers)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise FetchError(url, f"JSON 解析失败：{exc.msg}") from exc


def make_client(collector_config: Mapping[str, Any], config: Mapping[str, Any],
                logger: Optional[Callable[[str], None]] = None) -> HttpClient:
    """按 config.collector 构造客户端。"""
    collector = collector_config or {}
    return HttpClient(
        timeout=collector.get("timeoutSeconds", 20),
        retries=collector.get("retries", 2),
        user_agent=collector.get("userAgent", DEFAULT_USER_AGENT),
        interval=collector.get("requestIntervalSeconds", 0.35),
        proxy=(config or {}).get("proxy", "") or "",
        logger=logger,
    )
