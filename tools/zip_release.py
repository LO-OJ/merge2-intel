#!/usr/bin/env python3
"""Zip site/ for drag-and-drop static hosting.

Usage:
    python tools/zip_release.py
"""
from __future__ import annotations

import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
CN_TZ = timezone(timedelta(hours=8))


def main() -> int:
    if not (SITE / "index.html").exists():
        print("site/index.html 不存在，先运行 python tools/build.py")
        return 1
    stamp = datetime.now(CN_TZ).strftime("%Y%m%d-%H%M")
    out = ROOT / f"发布包-{stamp}.zip"
    count = 0
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(SITE.rglob("*")):
            if not path.is_file():
                continue
            archive.write(path, path.relative_to(SITE))
            count += 1
    print(f"已生成 {out.name}（{count} 个文件，{out.stat().st_size / 1024 / 1024:.2f} MB）")
    print("把解压后的 site 目录内容上传到任意静态托管即可。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
