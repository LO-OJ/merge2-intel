"""data/auto JSON 读写、原子写入与运行状态工具。

- 所有 JSON 原子写：先写 ``*.tmp`` 再 ``os.replace``；失败不破坏旧文件。
- 日期/时间统一 Asia/Shanghai（固定 +08:00，避免 Windows 缺 tzdata 时 ZoneInfo 失败）。
- 版本记录去重/裁剪等纯函数放在 appstore/charts/alerts，本模块只做通用读写。
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

ROOT = Path(__file__).resolve().parents[2]
AUTO_DIR = ROOT / "data" / "auto"
STATE_DIR = AUTO_DIR / "state"
TOOLS_DIR = ROOT / "tools"
CONFIG_PATH = TOOLS_DIR / "config.json"
LOGS_DIR = TOOLS_DIR / "logs"

CN_TZ = timezone(timedelta(hours=8))
DATE_FMT = "%Y-%m-%d"

EMPTY_VERSIONS = {"versions": [], "updatedAt": ""}
EMPTY_CHARTS = {"latest": [], "top5": [], "rankHistory": {}, "updatedAt": ""}
EMPTY_ALERTS = {"alerts": [], "updatedAt": ""}
EMPTY_STATUS = {"sources": {}, "updatedAt": ""}
EMPTY_DRAFTS = {"drafts": [], "updatedAt": ""}


# -- 时间 -----------------------------------------------------------------
def now_cn() -> datetime:
    return datetime.now(CN_TZ)


def now_iso() -> str:
    return now_cn().isoformat(timespec="seconds")


def today() -> date:
    return now_cn().date()


def today_str() -> str:
    return today().isoformat()


def date_str(value: Optional[date] = None) -> str:
    return (value or today()).isoformat()


def parse_date(value: Any) -> Optional[date]:
    """解析 YYYY-MM-DD；失败返回 None。"""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def iso_from_date(value: date) -> str:
    return value.isoformat()


# -- JSON 读写 ------------------------------------------------------------
def _default(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _default(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_default(item) for item in value]
    return value


def read_json(path: Path, default: Any = None) -> Any:
    """读 JSON；不存在或解析失败时返回 default 的深拷贝。"""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, IsADirectoryError):
        return _default(default)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return _default(default)


def write_json_atomic(path: Path, payload: Any) -> None:
    """原子写 UTF-8 JSON（不带 BOM）；失败时清理 tmp 并抛异常。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


# -- auto 数据读取 --------------------------------------------------------
def auto_path(filename: str) -> Path:
    return AUTO_DIR / filename


def load_versions(path: Optional[Path] = None) -> dict:
    data = read_json(path or auto_path("versions.json"), EMPTY_VERSIONS)
    if not isinstance(data, dict):
        data = _default(EMPTY_VERSIONS)
    if not isinstance(data.get("versions"), list):
        data["versions"] = []
    data.setdefault("updatedAt", "")
    return data


def load_charts(path: Optional[Path] = None) -> dict:
    data = read_json(path or auto_path("charts.json"), EMPTY_CHARTS)
    if not isinstance(data, dict):
        data = _default(EMPTY_CHARTS)
    if not isinstance(data.get("latest"), list):
        data["latest"] = []
    if not isinstance(data.get("top5"), list):
        data["top5"] = []
    if not isinstance(data.get("rankHistory"), dict):
        data["rankHistory"] = {}
    data.setdefault("updatedAt", "")
    return data


def load_alerts(path: Optional[Path] = None) -> dict:
    data = read_json(path or auto_path("alerts.json"), EMPTY_ALERTS)
    if not isinstance(data, dict):
        data = _default(EMPTY_ALERTS)
    if not isinstance(data.get("alerts"), list):
        data["alerts"] = []
    data.setdefault("updatedAt", "")
    return data


def load_source_status(path: Optional[Path] = None) -> dict:
    data = read_json(path or auto_path("source_status.json"), EMPTY_STATUS)
    if not isinstance(data, dict):
        data = _default(EMPTY_STATUS)
    if not isinstance(data.get("sources"), dict):
        data["sources"] = {}
    data.setdefault("updatedAt", "")
    return data


def load_state(name: str, default: Any = None) -> Any:
    """读 data/auto/state/<name>.json。"""
    return read_json(STATE_DIR / f"{name}.json", default if default is not None else {})


def save_state(name: str, payload: Any) -> Path:
    path = STATE_DIR / f"{name}.json"
    write_json_atomic(path, payload)
    return path


# -- 状态合并 -------------------------------------------------------------
def merge_source_status(existing: Mapping[str, Any], updates: Mapping[str, Any],
                        updated_at: Optional[str] = None) -> dict:
    """合并 source_status；同 key 覆盖，其他保留。"""
    sources = dict(existing.get("sources", {}) or {})
    for key, value in (updates or {}).items():
        if isinstance(value, dict):
            sources[key] = dict(value)
    return {"sources": sources, "updatedAt": updated_at or now_iso()}


def status_entry(ok: bool, items: int = 0, error: str = "",
                 last_run: Optional[str] = None) -> dict:
    return {
        "ok": bool(ok),
        "lastRun": last_run or now_iso(),
        "items": int(items),
        "error": error or "",
    }


# -- 其他小工具 -----------------------------------------------------------
def truncate(text: Any, limit: int = 2000) -> str:
    if not isinstance(text, str):
        return ""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def dedupe_by(items: Iterable[Mapping[str, Any]], key: str) -> list:
    """按字段去重，保留先出现的记录。"""
    seen = set()
    result = []
    for item in items:
        value = item.get(key) if isinstance(item, Mapping) else None
        if value in seen:
            continue
        seen.add(value)
        result.append(item)
    return result
