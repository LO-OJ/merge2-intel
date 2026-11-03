#!/usr/bin/env python3
"""Check whether curated item URLs are reachable.

Usage:
    python tools/check_links.py
    python tools/check_links.py --limit 30 --timeout 12
"""
from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import validate  # noqa: E402

CN_TZ = timezone(timedelta(hours=8))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"


def check(url: str, timeout: int) -> dict:
    result = {"url": url, "status": None, "ok": False, "error": "", "finalUrl": ""}
    ctx = ssl.create_default_context()
    insecure = ssl._create_unverified_context()  # only used after a cert failure
    for method in ("HEAD", "GET"):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": UA}, method=method)
            with urllib.request.urlopen(request, timeout=timeout, context=ctx) as response:
                result.update(status=response.status, ok=response.status < 400, finalUrl=response.geturl())
                return result
        except urllib.error.HTTPError as exc:
            result.update(status=exc.code, ok=exc.code < 400, error=f"HTTP {exc.code}")
            if exc.code not in (403, 405, 501):
                return result
        except urllib.error.URLError as exc:
            if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
                result.update(error=f"{type(exc).__name__}: {exc}")
                continue
            try:
                request = urllib.request.Request(url, headers={"User-Agent": UA}, method=method)
                with urllib.request.urlopen(request, timeout=timeout, context=insecure) as response:
                    result.update(status=response.status, ok=response.status < 400, finalUrl=response.geturl())
                    return result
            except Exception as inner:  # noqa: BLE001
                result.update(error=f"{type(inner).__name__}: {inner}")
        except ssl.SSLError:
            try:
                request = urllib.request.Request(url, headers={"User-Agent": UA}, method=method)
                with urllib.request.urlopen(request, timeout=timeout, context=insecure) as response:
                    result.update(status=response.status, ok=response.status < 400, finalUrl=response.geturl())
                    return result
            except Exception as exc:  # noqa: BLE001
                result.update(error=f"{type(exc).__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            result.update(error=f"{type(exc).__name__}: {exc}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="只检查前 N 条，0 表示全部")
    parser.add_argument("--timeout", type=int, default=12)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()

    curated, errors, warnings, _ = validate.load_curated()
    if errors:
        for error in errors:
            print(f"数据错误：{error}")
        return 1
    items = curated["items"]
    if args.limit:
        items = items[: args.limit]
    urls = []
    seen = set()
    for item in items:
        url = item.get("url")
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    if not urls:
        print("没有可检查的情报链接。")
        return 0

    print(f"检查 {len(urls)} 个链接（并发 {args.workers}）…")
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(check, url, args.timeout): url for url in urls}
        for index, future in enumerate(as_completed(futures), 1):
            result = future.result()
            results.append(result)
            mark = "OK " if result["ok"] else "FAIL"
            print(f"[{index}/{len(urls)}] {mark} {result['status']} {result['url']} {result['error']}")
    ok = sum(1 for result in results if result["ok"])
    report = {
        "checkedAt": datetime.now(CN_TZ).isoformat(timespec="seconds"),
        "total": len(results),
        "ok": ok,
        "failed": len(results) - ok,
        "results": results,
    }
    out_dir = ROOT / "data" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"links-{datetime.now(CN_TZ).strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n可达 {ok}/{len(results)}；报告：{out}")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
