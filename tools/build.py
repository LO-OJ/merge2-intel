#!/usr/bin/env python3
"""Build site/data/kb.js and site/data/charts.js from curated + auto data.

Usage:
    python tools/build.py
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))

import validate  # noqa: E402

CN_TZ = timezone(timedelta(hours=8))
SITE_DATA = ROOT / "site" / "data"
CONFIG_PATH = TOOLS_DIR / "config.json"
STORE_LABELS = {"cn": "中国区", "us": "美区", "jp": "日区", "kr": "韩区", "hk": "港区", "tw": "台区"}


def clean(obj):
    if isinstance(obj, dict):
        return {key: clean(value) for key, value in obj.items() if not str(key).startswith("_")}
    if isinstance(obj, list):
        return [clean(value) for value in obj]
    return obj


def read_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def parse_date(value: str):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def build_latest_versions(versions, games_by_id):
    latest = {}
    ordered = sorted(
        versions,
        key=lambda v: (v.get("releasedAt") or "", v.get("fetchedAt") or "", v.get("version") or ""),
        reverse=True,
    )
    for version in ordered:
        game_id = version.get("gameId")
        store = version.get("store")
        if not game_id or not store:
            continue
        latest.setdefault(game_id, {})
        latest[game_id].setdefault(store, version)
    for game_id, stores in latest.items():
        game = games_by_id.get(game_id)
        for store, version in stores.items():
            version["storeLabel"] = STORE_LABELS.get(store, store)
            if game:
                version["gameName"] = game.get("nameZh") or game.get("name")
    return latest


def build_stats(items, games, sources, alerts, drafts, versions) -> dict:
    today = datetime.now(CN_TZ).date()
    by_dimension: dict[str, int] = {}
    by_game: dict[str, int] = {}
    by_source: dict[str, int] = {}
    by_month: dict[str, int] = {}
    recent7 = recent30 = 0
    last_date = None
    for item in items:
        for dim in item.get("dimensions", []) or []:
            by_dimension[dim] = by_dimension.get(dim, 0) + 1
        for game_id in item.get("gameIds", []) or []:
            by_game[game_id] = by_game.get(game_id, 0) + 1
        source_id = item.get("sourceId")
        if source_id:
            by_source[source_id] = by_source.get(source_id, 0) + 1
        parsed = parse_date(item.get("publishedAt", ""))
        if parsed:
            month = parsed.strftime("%Y-%m")
            by_month[month] = by_month.get(month, 0) + 1
            if last_date is None or parsed > last_date:
                last_date = parsed
            delta = (today - parsed).days
            if 0 <= delta <= 6:
                recent7 += 1
            if 0 <= delta <= 29:
                recent30 += 1
    return {
        "items": len(items),
        "selfGames": sum(1 for g in games if g.get("role") == "self"),
        "competitors": sum(1 for g in games if g.get("role") == "competitor"),
        "watchGames": sum(1 for g in games if g.get("role") == "watch"),
        "sources": len(sources),
        "versions": len(versions),
        "alerts": len(alerts),
        "drafts": len(drafts),
        "recent7": recent7,
        "recent30": recent30,
        "byDimension": dict(sorted(by_dimension.items(), key=lambda kv: (-kv[1], kv[0]))),
        "byGame": dict(sorted(by_game.items(), key=lambda kv: (-kv[1], kv[0]))),
        "bySource": dict(sorted(by_source.items(), key=lambda kv: (-kv[1], kv[0]))),
        "byMonth": dict(sorted(by_month.items())),
        "lastItemDate": last_date.isoformat() if last_date else "",
    }


def attach_source_status(sources, raw_status):
    """Map collector status keys (itunes_lookup_*, charts_*, rss_*) onto source ids."""
    raw_status = raw_status or {}

    def aggregate(keys):
        rows = [raw_status[key] for key in keys if key in raw_status]
        if not rows:
            return None
        last_runs = [row.get("lastRun") for row in rows if row.get("lastRun")]
        errors = [row.get("error") for row in rows if row.get("error")]
        return {
            "ok": all(row.get("ok") for row in rows),
            "lastRun": max(last_runs) if last_runs else "",
            "items": sum(int(row.get("items") or 0) for row in rows),
            "error": "；".join(errors)[:300],
        }

    for source in sources:
        source_id = source.get("id") or ""
        if source_id == "apple-appstore":
            keys = [key for key in raw_status if key.startswith("itunes_lookup")]
        elif source_id == "apple-charts":
            keys = [key for key in raw_status if key.startswith("charts_")]
        else:
            key = "rss_" + source_id
            keys = [key] if key in raw_status else []
        source["status"] = aggregate(keys)
    return raw_status


def write_js(path: Path, variable: str, payload) -> int:
    text = f"window.{variable} = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n"
    text = text.replace("</", "<\\/")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    return len(text.encode("utf-8"))


def main() -> int:
    validation = validate.validate_all()
    if validation["errors"]:
        print(f"构建中止：数据校验有 {len(validation['errors'])} 个错误。")
        for error in validation["errors"][:50]:
            print(f"  x {error}")
        if len(validation["errors"]) > 50:
            print(f"  ... 另有 {len(validation['errors']) - 50} 个错误")
        return 2

    curated, _, _, _ = validate.load_curated()
    auto, _, _ = validate.load_auto()
    config = read_config()

    games = clean(curated["games"])
    items = clean(curated["items"])
    sources = clean(curated["sources"])
    playbook = clean(curated["playbook"])
    digests = clean(curated["digests"])
    versions = clean(curated["versions"]) + clean(auto["versions"].get("versions", []))
    alerts = clean(auto["alerts"].get("alerts", []))
    drafts = clean(auto["drafts"].get("drafts", []))
    charts = clean(auto["charts"])
    source_status = clean(auto["source_status"].get("sources", {}))
    auto_items = clean(auto["items_auto"].get("items", []))
    items.extend(auto_items)

    # 去重（curated 优先，auto 只补充不存在的 id）
    seen_item_ids = set()
    deduped_items = []
    for item in items:
        item_id = item.get("id")
        if item_id in seen_item_ids:
            continue
        seen_item_ids.add(item_id)
        deduped_items.append(item)
    items = deduped_items

    games_by_id = {g.get("id"): g for g in games if g.get("id")}
    sources_by_id = {s.get("id"): s for s in sources if s.get("id")}

    for game in games:
        game_id = game.get("id")
        game["itemCount"] = sum(1 for item in items if game_id in (item.get("gameIds") or []))

    for item in items:
        source = sources_by_id.get(item.get("sourceId"))
        if source:
            item["sourceName"] = source.get("name")
            item["sourceType"] = source.get("type")
        item["gameNames"] = [
            games_by_id[gid].get("nameZh") or games_by_id[gid].get("name")
            for gid in item.get("gameIds", []) or []
            if gid in games_by_id
        ]

    for alert in alerts:
        game = games_by_id.get(alert.get("gameId"))
        if game:
            alert["gameName"] = game.get("nameZh") or game.get("name")

    for draft in drafts:
        source = sources_by_id.get(draft.get("sourceId"))
        if source:
            draft["sourceName"] = source.get("name")

    latest_versions = build_latest_versions(versions, games_by_id)
    for game in games:
        game["latestVersion"] = latest_versions.get(game.get("id"), {})

    source_status = attach_source_status(sources, source_status)

    for source in sources:
        source["itemCount"] = sum(1 for item in items if item.get("sourceId") == source.get("id"))

    items.sort(key=lambda i: (i.get("publishedAt") or "", i.get("importance") or 0, i.get("id") or ""), reverse=True)
    versions.sort(key=lambda v: (v.get("releasedAt") or "", v.get("fetchedAt") or "", v.get("version") or ""), reverse=True)
    alerts.sort(key=lambda a: (a.get("date") or "", a.get("id") or ""), reverse=True)
    drafts.sort(key=lambda d: (d.get("publishedAt") or "", d.get("fetchedAt") or ""), reverse=True)
    playbook.sort(key=lambda s: (s.get("title") or ""))
    digests.sort(key=lambda d: (d.get("start") or "", d.get("id") or ""), reverse=True)

    charts.setdefault("latest", [])
    charts.setdefault("top5", [])
    charts.setdefault("rankHistory", {})
    charts["latest"] = sorted(
        charts["latest"],
        key=lambda s: (s.get("country") or "", s.get("kindId") or ""),
    )
    charts["top5"] = sorted(
        charts["top5"],
        key=lambda s: (s.get("date") or "", s.get("country") or "", s.get("kindId") or ""),
        reverse=True,
    )[:90 * 12]

    now = datetime.now(CN_TZ)
    stats = build_stats(items, games, sources, alerts, drafts, versions)
    site_cfg = config.get("site", {})
    meta = {
        "siteName": site_cfg.get("name", "二合情报站"),
        "siteNameEn": site_cfg.get("nameEn", "Merge-2 Radar"),
        "generatedAt": now.isoformat(timespec="seconds"),
        "buildId": now.strftime("%Y%m%d-%H%M%S"),
        "timezone": "Asia/Shanghai",
        "itemCount": stats["items"],
        "gameCount": len(games),
        "sourceCount": len(sources),
        "playbookCount": len(playbook),
        "digestCount": len(digests),
        "disclaimer": site_cfg.get("disclaimer", ""),
        "dataUpdatedAt": charts.get("updatedAt") or auto["versions"].get("updatedAt") or "",
        "aiStatus": (source_status or {}).get("ai"),
        "stats": stats,
    }
    kb = {
        "meta": meta,
        "games": games,
        "items": items,
        "sources": sources,
        "playbook": playbook,
        "digests": digests,
        "versions": versions,
        "latestVersions": latest_versions,
        "alerts": alerts,
        "drafts": drafts,
        "sourceStatus": source_status,
        "stats": stats,
    }

    size_kb = write_js(SITE_DATA / "kb.js", "KB", kb)
    size_charts = write_js(SITE_DATA / "charts.js", "KB_CHARTS", charts)
    print(
        "构建完成："
        f"items={len(items)} games={len(games)} playbook={len(playbook)} digests={len(digests)} "
        f"versions={len(versions)} alerts={len(alerts)} drafts={len(drafts)}"
    )
    print(f"  site/data/kb.js     {size_kb / 1024:.1f} KB")
    print(f"  site/data/charts.js {size_charts / 1024:.1f} KB")
    print(f"  buildId={meta['buildId']}")
    if validation["warnings"]:
        print(f"  警告 {len(validation['warnings'])} 条（运行 python tools/validate.py 查看）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
