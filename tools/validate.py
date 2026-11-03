#!/usr/bin/env python3
"""Validate curated + auto data against docs/DATA_SCHEMA.md.

Usage:
    python tools/validate.py
    python tools/validate.py --json
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from itertools import chain
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CURATED_DIR = ROOT / "data" / "curated"
AUTO_DIR = ROOT / "data" / "auto"

CN_TZ = timezone(timedelta(hours=8))
TODAY = datetime.now(CN_TZ).date()

DIMENSIONS = {
    "activity", "system", "launch", "monetization", "economy",
    "market", "ua", "publisher", "version",
}
ROLES = {"self", "competitor", "watch"}
CONFIDENCE = {"high", "medium", "low"}
SUMMARY_BY = {"editor", "ai"}
ALERT_TYPES = {"top5", "new-entry", "rank-jump", "version", "suspect-hit"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WEEK_RE = re.compile(r"^\d{4}-W\d{2}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,90}$")
SECRET_RE = re.compile(r"sk-[A-Za-z0-9]{20,}")
BAD_HTML_RE = re.compile(r"<\s*(script|iframe|object|embed)\b", re.I)

REQUIRED_GAME = ("id", "name", "publisher", "role")
REQUIRED_ITEM = (
    "id", "title", "summary", "takeaway", "dimensions", "sourceId",
    "url", "publishedAt", "importance", "confidence", "summaryBy",
)
REQUIRED_SOURCE = ("id", "name", "type", "url", "auto")


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"{path.name}: 文件不存在"
    except json.JSONDecodeError as exc:
        return None, f"{path.name}: JSON 解析失败（第 {exc.lineno} 行第 {exc.colno} 列）：{exc.msg}"


def _walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from _walk_strings(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _walk_strings(value)


def valid_date(value: str) -> bool:
    if not isinstance(value, str) or not DATE_RE.match(value):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def valid_url(value: str) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def load_curated():
    """Load and merge every data/curated/*.json.

    Returns (data, errors, warnings, files).
    Each entity gets a private ``_file`` key used only for error reporting.
    """
    data = {
        "games": [], "items": [], "sources": [], "playbook": [],
        "digests": [], "versions": [], "meta": {},
    }
    errors: list[str] = []
    warnings: list[str] = []
    files = sorted(CURATED_DIR.glob("*.json"))
    if not files:
        warnings.append("data/curated/ 下没有任何 JSON 文件")
    for path in files:
        obj, err = load_json(path)
        if err:
            errors.append(err)
            continue
        if not isinstance(obj, dict):
            errors.append(f"{path.name}: 顶层必须是对象")
            continue
        for key, bucket in data.items():
            if key not in obj:
                continue
            value = obj[key]
            if key == "meta":
                if not isinstance(value, dict):
                    errors.append(f"{path.name}: meta 必须是对象")
                else:
                    bucket.update(value)
                continue
            if not isinstance(value, list):
                errors.append(f"{path.name}: {key} 必须是数组")
                continue
            for index, entry in enumerate(value):
                if not isinstance(entry, dict):
                    errors.append(f"{path.name}: {key}[{index}] 必须是对象")
                    continue
                item = dict(entry)
                item["_file"] = path.name
                bucket.append(item)
    return data, errors, warnings, [p.name for p in files]


DEFAULTS = {
    "latest": [],
    "top5": [],
    "rankHistory": {},
    "updatedAt": "",
}


def load_auto():
    data = {
        "versions": {"versions": [], "updatedAt": ""},
        "charts": dict(DEFAULTS),
        "alerts": {"alerts": [], "updatedAt": ""},
        "drafts": {"drafts": [], "updatedAt": ""},
        "source_status": {"sources": {}, "updatedAt": ""},
        "items_auto": {"items": [], "updatedAt": ""},
    }
    errors: list[str] = []
    warnings: list[str] = []
    mapping = {
        "versions.json": "versions",
        "charts.json": "charts",
        "alerts.json": "alerts",
        "drafts.json": "drafts",
        "source_status.json": "source_status",
        "items-auto.json": "items_auto",
    }
    for filename, key in mapping.items():
        path = AUTO_DIR / filename
        if not path.exists():
            continue
        obj, err = load_json(path)
        if err:
            errors.append(err)
            continue
        if not isinstance(obj, dict):
            errors.append(f"{filename}: 顶层必须是对象")
            continue
        if key == "charts":
            for field, default in DEFAULTS.items():
                data["charts"][field] = obj.get(field, default)
            if not isinstance(data["charts"]["latest"], list):
                errors.append("charts.json: latest 必须是数组")
                data["charts"]["latest"] = []
            if not isinstance(data["charts"]["top5"], list):
                errors.append("charts.json: top5 必须是数组")
                data["charts"]["top5"] = []
            if not isinstance(data["charts"]["rankHistory"], dict):
                errors.append("charts.json: rankHistory 必须是对象")
                data["charts"]["rankHistory"] = {}
        else:
            for field in ("versions", "alerts", "drafts", "items"):
                if field in obj:
                    data[key][field] = obj[field]
            if "sources" in obj:
                data["source_status"]["sources"] = obj["sources"]
            data[key]["updatedAt"] = obj.get("updatedAt", "")
    return data, errors, warnings


def _check_text(errors: list[str], where: str, text, required: bool = True):
    if text is None:
        if required:
            errors.append(f"{where}: 不能为空")
        return
    if not isinstance(text, str):
        errors.append(f"{where}: 必须是字符串")
        return
    if required and not text.strip():
        errors.append(f"{where}: 不能为空")
    if BAD_HTML_RE.search(text):
        errors.append(f"{where}: 含有不允许的 HTML 标签")
    if SECRET_RE.search(text):
        errors.append(f"{where}: 疑似包含密钥，请删除")


def _ids(entities, key, label, errors, warnings, pattern=SLUG_RE):
    seen = set()
    for index, entity in enumerate(entities):
        value = entity.get(key) if isinstance(entity, dict) else None
        where = f"{label}[{index}]"
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{where}: 缺少 {key}")
            continue
        if pattern and not pattern.match(value):
            errors.append(f"{where}: {key}={value!r} 格式不合法（应为小写 slug）")
        if value in seen:
            errors.append(f"{where}: {key}={value!r} 重复")
        seen.add(value)
    return seen


def validate_games(games, errors, warnings):
    ids = _ids(games, "id", "games", errors, warnings)
    for game in games:
        where = f"游戏 {game.get('id', '?')} ({game.get('_file', '?')})"
        for field in REQUIRED_GAME:
            if not game.get(field):
                errors.append(f"{where}: 缺少 {field}")
        if game.get("role") not in ROLES:
            errors.append(f"{where}: role 必须是 {sorted(ROLES)} 之一")
        stores = game.get("stores", {})
        if not isinstance(stores, dict):
            errors.append(f"{where}: stores 必须是对象")
        else:
            for store, app_id in stores.items():
                if store not in {"cn", "us", "jp", "kr", "hk", "tw"}:
                    warnings.append(f"{where}: 未知商店 {store}")
                if not re.fullmatch(r"\d{5,12}", str(app_id)):
                    errors.append(f"{where}: stores.{store} 的 appId 不合法")
        for field in ("coreLoop", "monetization", "notableSystems", "borrow", "risks", "tags", "sourceUrls"):
            value = game.get(field, [])
            if value is not None and not isinstance(value, list):
                errors.append(f"{where}: {field} 必须是数组")
        for url in game.get("sourceUrls", []) or []:
            if not valid_url(url):
                errors.append(f"{where}: sourceUrls 中有非法 URL: {url!r}")
        matrix = game.get("matrix")
        if matrix is not None and not isinstance(matrix, dict):
            errors.append(f"{where}: matrix 必须是对象")
    return ids


def validate_sources(sources, errors, warnings):
    ids = _ids(sources, "id", "sources", errors, warnings)
    allowed_types = {
        "官方", "榜单", "数据", "数据/榜单", "数据/买量", "数据/资料",
        "行业媒体", "游戏媒体", "社区", "拆解/分析", "分析", "厂商",
    }
    for source in sources:
        where = f"来源 {source.get('id', '?')} ({source.get('_file', '?')})"
        for field in REQUIRED_SOURCE:
            if source.get(field) in (None, ""):
                errors.append(f"{where}: 缺少 {field}")
        if source.get("type") and source["type"] not in allowed_types:
            warnings.append(f"{where}: type={source['type']!r} 不在推荐枚举中")
        if not valid_url(source.get("url", "")):
            errors.append(f"{where}: url 不合法")
        if source.get("feed") and not valid_url(source["feed"]):
            errors.append(f"{where}: feed 不合法")
        if not isinstance(source.get("auto"), bool):
            errors.append(f"{where}: auto 必须是布尔值")
    return ids


def validate_items(items, game_ids, source_ids, errors, warnings):
    ids = _ids(items, "id", "items", errors, warnings)
    urls = {}
    for item in items:
        where = f"情报 {item.get('id', '?')} ({item.get('_file', '?')})"
        for field in REQUIRED_ITEM:
            if field not in item or item.get(field) in (None, "", []):
                errors.append(f"{where}: 缺少 {field}")
        for field in ("id", "title", "summary", "takeaway", "sourceId", "url"):
            _check_text(errors, f"{where}.{field}", item.get(field))
        if item.get("dimensions"):
            dims = item["dimensions"]
            if not isinstance(dims, list):
                errors.append(f"{where}: dimensions 必须是数组")
            else:
                for dim in dims:
                    if dim not in DIMENSIONS:
                        errors.append(f"{where}: 未知维度 {dim!r}")
        if item.get("importance") not in (1, 2, 3):
            errors.append(f"{where}: importance 必须是 1/2/3")
        if item.get("confidence") not in CONFIDENCE:
            errors.append(f"{where}: confidence 非法")
        if item.get("summaryBy") not in SUMMARY_BY:
            errors.append(f"{where}: summaryBy 非法")
        if not valid_date(item.get("publishedAt", "")):
            errors.append(f"{where}: publishedAt 必须是 YYYY-MM-DD")
        elif date.fromisoformat(item["publishedAt"]) > TODAY + timedelta(days=1):
            warnings.append(f"{where}: publishedAt 在未来")
        if not valid_url(item.get("url", "")):
            errors.append(f"{where}: url 不合法")
        else:
            urls.setdefault(item["url"], []).append(item.get("id"))
        if item.get("sourceId") and item["sourceId"] not in source_ids:
            errors.append(f"{where}: sourceId={item['sourceId']!r} 不在来源目录")
        game_ids_value = item.get("gameIds", [])
        if not isinstance(game_ids_value, list):
            errors.append(f"{where}: gameIds 必须是数组")
        else:
            for game_id in game_ids_value:
                if game_id not in game_ids:
                    errors.append(f"{where}: gameIds 引用了不存在的游戏 {game_id!r}")
        summary = item.get("summary") or ""
        takeaway = item.get("takeaway") or ""
        if isinstance(summary, str) and not (20 <= len(summary) <= 500):
            warnings.append(f"{where}: summary 长度 {len(summary)}，建议 80–150 字")
        if isinstance(takeaway, str) and not (5 <= len(takeaway) <= 400):
            warnings.append(f"{where}: takeaway 长度 {len(takeaway)}，建议具体到 1–2 条动作")
        tags = item.get("tags", [])
        if tags is not None and not isinstance(tags, list):
            errors.append(f"{where}: tags 必须是数组")
        if item.get("datePrecision") not in (None, "day", "month", "year"):
            errors.append(f"{where}: datePrecision 非法")
    for url, item_ids in urls.items():
        if len(item_ids) > 1:
            warnings.append(f"重复 URL：{url} 被 {item_ids} 引用")
    return ids


def validate_playbook(playbook, item_ids, game_ids, errors, warnings):
    ids = _ids(playbook, "id", "playbook", errors, warnings)
    for section in playbook:
        where = f"拆解 {section.get('id', '?')} ({section.get('_file', '?')})"
        for field in ("title", "dimension", "summary"):
            if not section.get(field):
                errors.append(f"{where}: 缺少 {field}")
        if section.get("dimension") not in DIMENSIONS:
            errors.append(f"{where}: dimension 非法")
        principles = section.get("principles", [])
        if not isinstance(principles, list) or not principles:
            errors.append(f"{where}: principles 必须是非空数组")
        else:
            for index, principle in enumerate(principles):
                pwhere = f"{where}.principles[{index}]"
                if not isinstance(principle, dict):
                    errors.append(f"{pwhere}: 必须是对象")
                    continue
                for field in ("title", "detail"):
                    if not principle.get(field):
                        errors.append(f"{pwhere}: 缺少 {field}")
                for evidence in principle.get("evidence", []) or []:
                    if evidence not in item_ids:
                        errors.append(f"{pwhere}: evidence={evidence!r} 不存在")
        cases = section.get("cases", [])
        if cases is not None and not isinstance(cases, list):
            errors.append(f"{where}: cases 必须是数组")
        else:
            for index, case in enumerate(cases or []):
                if not isinstance(case, dict):
                    errors.append(f"{where}.cases[{index}]: 必须是对象")
                    continue
                if case.get("gameId") and case["gameId"] not in game_ids:
                    errors.append(f"{where}.cases[{index}]: gameId 不存在")
                if case.get("sourceUrl") and not valid_url(case["sourceUrl"]):
                    errors.append(f"{where}.cases[{index}]: sourceUrl 不合法")
        checklist = section.get("checklist", [])
        if not isinstance(checklist, list) or not checklist:
            errors.append(f"{where}: checklist 必须是非空数组")
    return ids


def validate_digests(digests, item_ids, errors, warnings):
    ids = _ids(digests, "id", "digests", errors, warnings, pattern=None)
    for digest in digests:
        where = f"周报 {digest.get('id', '?')} ({digest.get('_file', '?')})"
        for field in ("week", "start", "end", "headline", "overview"):
            if not digest.get(field):
                errors.append(f"{where}: 缺少 {field}")
        if digest.get("week") and not WEEK_RE.match(digest["week"]):
            errors.append(f"{where}: week 必须形如 2026-W45")
        for field in ("start", "end"):
            if digest.get(field) and not valid_date(digest[field]):
                errors.append(f"{where}: {field} 必须是 YYYY-MM-DD")
        for item_id in digest.get("topItemIds", []) or []:
            if item_id not in item_ids:
                errors.append(f"{where}: topItemIds 引用了不存在的情报 {item_id!r}")
        if not isinstance(digest.get("actions", []), list):
            errors.append(f"{where}: actions 必须是数组")
    return ids


def validate_versions(versions, game_ids, errors, warnings):
    ids = _ids(versions, "id", "versions", errors, warnings, pattern=None)
    for version in versions:
        where = f"版本 {version.get('id', '?')} ({version.get('_file', 'versions.json')})"
        if version.get("gameId") not in game_ids:
            errors.append(f"{where}: gameId 不存在")
        if version.get("store") not in {"cn", "us", "jp", "kr", "hk", "tw"}:
            errors.append(f"{where}: store 非法")
        if not version.get("version"):
            errors.append(f"{where}: 缺少 version")
        released = version.get("releasedAt", "")
        if released and not valid_date(released):
            errors.append(f"{where}: releasedAt 必须是 YYYY-MM-DD")
        if version.get("notes") is not None and not isinstance(version["notes"], str):
            errors.append(f"{where}: notes 必须是字符串")
    return ids


def validate_alerts(alerts, game_ids, errors):
    ids = _ids(alerts, "id", "alerts", errors, [], pattern=None)
    for alert in alerts:
        where = f"告警 {alert.get('id', '?')}"
        if alert.get("type") not in ALERT_TYPES:
            errors.append(f"{where}: type 非法")
        if alert.get("date") and not valid_date(alert["date"]):
            errors.append(f"{where}: date 必须是 YYYY-MM-DD")
        if alert.get("gameId") and alert["gameId"] not in game_ids:
            errors.append(f"{where}: gameId 不存在")
    return ids


def validate_drafts(drafts, errors):
    ids = _ids(drafts, "id", "drafts", errors, [], pattern=None)
    for draft in drafts:
        where = f"线索 {draft.get('id', '?')}"
        if not draft.get("title"):
            errors.append(f"{where}: 缺少 title")
        if not valid_url(draft.get("url", "")):
            errors.append(f"{where}: url 不合法")
        if draft.get("publishedAt") and not valid_date(draft["publishedAt"]):
            errors.append(f"{where}: publishedAt 必须是 YYYY-MM-DD")
    return ids


def validate_charts(charts, game_ids, errors):
    latest = charts.get("latest", [])
    if not isinstance(latest, list):
        errors.append("charts.latest 必须是数组")
        return
    for snapshot in latest:
        if not isinstance(snapshot, dict):
            errors.append("charts.latest 中存在非对象")
            continue
        for field in ("date", "country", "kindId", "entries"):
            if field not in snapshot:
                errors.append(f"charts.latest 快照缺少 {field}")
        if snapshot.get("date") and not valid_date(snapshot["date"]):
            errors.append("charts.latest 快照 date 非法")
        entries = snapshot.get("entries")
        if not isinstance(entries, list):
            errors.append("charts.latest.entries 必须是数组")
            continue
        for entry in entries[:3]:
            if not isinstance(entry, dict) or "rank" not in entry or "appId" not in entry:
                errors.append("charts.latest.entries 条目缺少 rank/appId")
                break
    top5 = charts.get("top5", [])
    if not isinstance(top5, list):
        errors.append("charts.top5 必须是数组")
    else:
        for snapshot in top5[:5]:
            if not isinstance(snapshot, dict) or "entries" not in snapshot:
                errors.append("charts.top5 条目缺少 entries")
                break
    history = charts.get("rankHistory", {})
    if not isinstance(history, dict):
        errors.append("charts.rankHistory 必须是对象")
    else:
        for game_id in history:
            if game_id not in game_ids:
                errors.append(f"charts.rankHistory 引用了不存在的游戏 {game_id!r}")


def validate_all():
    curated, errors, warnings, files = load_curated()
    auto, auto_errors, auto_warnings = load_auto()
    errors.extend(auto_errors)
    warnings.extend(auto_warnings)

    game_ids = validate_games(curated["games"], errors, warnings)
    source_ids = validate_sources(curated["sources"], errors, warnings)
    item_ids = validate_items(curated["items"], game_ids, source_ids, errors, warnings)
    validate_playbook(curated["playbook"], item_ids, game_ids, errors, warnings)
    validate_digests(curated["digests"], item_ids, errors, warnings)
    validate_versions(curated["versions"], game_ids, errors, warnings)
    validate_versions(auto["versions"].get("versions", []), game_ids, errors, warnings)
    validate_alerts(auto["alerts"].get("alerts", []), game_ids, errors)
    validate_drafts(auto["drafts"].get("drafts", []), errors)
    validate_charts(auto["charts"], game_ids, errors)
    validate_items(auto["items_auto"].get("items", []), game_ids, source_ids, errors, warnings)

    if not curated["items"]:
        warnings.append("还没有任何情报条目")
    if not curated["playbook"]:
        warnings.append("还没有拆解章节")
    if not curated["digests"]:
        warnings.append("还没有周报")

    for text in chain(_walk_strings(curated), _walk_strings(auto)):
        if SECRET_RE.search(text):
            errors.append("数据中疑似包含密钥（sk-…），请立即删除")
            break

    # 全局唯一性（跨类型不强制，仅同类检查）
    return {
        "errors": errors,
        "warnings": warnings,
        "files": files,
        "counts": {
            "games": len(curated["games"]),
            "selfGames": sum(1 for g in curated["games"] if g.get("role") == "self"),
            "competitors": sum(1 for g in curated["games"] if g.get("role") == "competitor"),
            "sources": len(curated["sources"]),
            "items": len(curated["items"]),
            "playbook": len(curated["playbook"]),
            "digests": len(curated["digests"]),
            "versions": len(auto["versions"].get("versions", [])),
            "alerts": len(auto["alerts"].get("alerts", [])),
            "drafts": len(auto["drafts"].get("drafts", [])),
        },
    }


def main() -> int:
    result = validate_all()
    counts = result["counts"]
    print("数据校验：", "，".join(f"{k}={v}" for k, v in counts.items()))
    print(f"文件：{', '.join(result['files']) or '(无)'}")
    if result["warnings"]:
        print(f"\n警告 {len(result['warnings'])} 条：")
        for warning in result["warnings"][:30]:
            print(f"  ! {warning}")
        if len(result["warnings"]) > 30:
            print(f"  ... 另有 {len(result['warnings']) - 30} 条")
    if result["errors"]:
        print(f"\n错误 {len(result['errors'])} 条：")
        for error in result["errors"]:
            print(f"  x {error}")
        return 1
    print("\n校验通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
