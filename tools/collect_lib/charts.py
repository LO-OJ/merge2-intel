"""App Store 榜单抓取与 charts.json 合并。

接口：
- ``https://itunes.apple.com/{country}/rss/{kind}/limit=50/json``
- ``https://itunes.apple.com/{country}/rss/{kind}/limit=50/genre={genre}/json``

解析 ``feed.entry`` 顺序即排名；合并规则：
- latest：每个 国家×榜单 一条，本次抓到的覆盖旧的，抓取失败的保留旧快照；
- top5：同日同 国家×榜单 覆盖而不是重复，保留最近 historyDays 天；
- rankHistory：只记录 config 游戏 appId 命中项，按日期去重，保留最近 historyDays 天。
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

from . import http as http_mod
from . import store

CHART_URL = "https://itunes.apple.com/{country}/rss/{kind}/limit={limit}{genre_part}/json"
DEFAULT_LIMIT = 50
HISTORY_DAYS = 90
TOP5_DAYS = 90


# -- URL 与解析 -----------------------------------------------------------
def chart_url(country: str, kind: str, genre: Optional[int] = None, limit: int = DEFAULT_LIMIT) -> str:
    genre_part = f"/genre={genre}" if genre not in (None, "", 0) else ""
    return CHART_URL.format(country=country, kind=kind, limit=limit, genre_part=genre_part)


def _label(container: Any) -> str:
    if isinstance(container, dict):
        return str(container.get("label") or "").strip()
    if isinstance(container, str):
        return container.strip()
    return ""


def parse_chart_entry(entry: Mapping[str, Any], rank: int) -> dict:
    app_id = ""
    identifier = entry.get("id")
    if isinstance(identifier, dict):
        attributes = identifier.get("attributes") or {}
        app_id = str(attributes.get("im:id") or "").strip()
        if not app_id:
            label = str(identifier.get("label") or "")
            # 部分情况下 label 是完整 URL，取最后一段（id123456789）
            tail = label.rstrip("/").rsplit("/", 1)[-1]
            if tail.startswith("id"):
                app_id = tail[2:]
    return {
        "rank": rank,
        "appId": app_id,
        "name": _label(entry.get("im:name")),
        "publisher": _label(entry.get("im:artist")),
    }


def parse_chart_feed(payload: Any) -> List[dict]:
    """把 RSS JSON 转成 [{rank, appId, name, publisher}]（按 feed 顺序编号）。"""
    if not isinstance(payload, dict):
        return []
    feed = payload.get("feed")
    if not isinstance(feed, dict):
        return []
    raw_entries = feed.get("entry")
    if isinstance(raw_entries, dict):
        raw_entries = [raw_entries]
    if not isinstance(raw_entries, list):
        return []
    entries = []
    for index, entry in enumerate(raw_entries, start=1):
        if isinstance(entry, dict):
            parsed = parse_chart_entry(entry, index)
            if parsed["appId"] or parsed["name"]:
                entries.append(parsed)
    return entries


# -- 抓取 -----------------------------------------------------------------
def fetch_charts(client: http_mod.HttpClient, config: Mapping[str, Any],
                 logger: Optional[Callable[[str], None]] = None,
                 today_value: Optional[date] = None) -> Tuple[List[dict], Dict[str, dict]]:
    """抓取 config.charts 下所有 国家×榜单；单源失败隔离。返回 (快照列表, source_status)。"""
    log = logger or (lambda _message: None)
    charts_cfg = config.get("charts") or {}
    countries = charts_cfg.get("countries") or ["us"]
    kinds = charts_cfg.get("kinds") or []
    limit = int(charts_cfg.get("limit") or DEFAULT_LIMIT)
    date_value = (today_value or store.today()).isoformat()
    snapshots: List[dict] = []
    statuses: Dict[str, dict] = {}
    for country in countries:
        for kind_cfg in kinds:
            kind_id = str(kind_cfg.get("id") or kind_cfg.get("kind") or "")
            kind = str(kind_cfg.get("kind") or "")
            genre = kind_cfg.get("genre")
            source_key = f"charts_{country}_{kind_id}"
            url = chart_url(country, kind, genre, limit)
            try:
                payload = client.get_json(url)
                entries = parse_chart_feed(payload)
                if not entries:
                    raise ValueError("feed.entry 为空或格式不符")
                snapshot = {
                    "date": date_value,
                    "country": country,
                    "kindId": kind_id,
                    "kind": kind,
                    "genre": genre,
                    "label": str(kind_cfg.get("label") or ""),
                    "entries": entries,
                }
                snapshots.append(snapshot)
                statuses[source_key] = store.status_entry(True, items=len(entries))
                log(f"  榜单 {country}/{kind_id}: {len(entries)} 条")
            except Exception as exc:  # 单源失败不阻断
                statuses[source_key] = store.status_entry(
                    False, items=0, error=f"{type(exc).__name__}: {exc}"
                )
                log(f"  榜单 {country}/{kind_id} 失败：{type(exc).__name__}: {exc}")
    return snapshots, statuses


# -- 合并 -----------------------------------------------------------------
def _snapshot_key(snapshot: Mapping[str, Any]) -> Tuple[str, str]:
    return str(snapshot.get("country") or ""), str(snapshot.get("kindId") or "")


def _trim_date_list(entries: List[list], days: int, today_value: date) -> List[list]:
    cutoff = today_value - timedelta(days=max(0, days))
    kept = []
    for entry in entries:
        parsed = store.parse_date(entry[0]) if isinstance(entry, (list, tuple)) and entry else None
        if parsed is not None and parsed >= cutoff:
            kept.append([entry[0], entry[1]])
    return kept


def _top5_snapshot(snapshot: Mapping[str, Any]) -> dict:
    entries = [
        {
            "rank": entry.get("rank"),
            "appId": entry.get("appId"),
            "name": entry.get("name"),
            "publisher": entry.get("publisher"),
        }
        for entry in (snapshot.get("entries") or [])[:5]
    ]
    return {
        "date": snapshot.get("date"),
        "country": snapshot.get("country"),
        "kindId": snapshot.get("kindId"),
        "entries": entries,
    }


def merge_charts(existing: Mapping[str, Any], snapshots: Iterable[Mapping[str, Any]],
                 games: Iterable[Mapping[str, Any]], today_value: Optional[date] = None,
                 history_days: int = HISTORY_DAYS, top5_days: int = TOP5_DAYS,
                 updated_at: Optional[str] = None) -> dict:
    """把本轮快照合并进 charts 结构（纯函数，便于测试）。"""
    today_value = today_value or store.today()
    updated_at = updated_at or store.now_iso()
    snapshots = [item for item in snapshots or [] if isinstance(item, Mapping)]
    existing = existing if isinstance(existing, Mapping) else {}

    # latest：本次抓到的覆盖同 国家×榜单；未抓到的保留旧快照
    latest_map: Dict[Tuple[str, str], dict] = {}
    for snapshot in existing.get("latest") or []:
        if isinstance(snapshot, Mapping):
            latest_map[_snapshot_key(snapshot)] = dict(snapshot)
    for snapshot in snapshots:
        latest_map[_snapshot_key(snapshot)] = dict(snapshot)
    latest = sorted(latest_map.values(), key=lambda item: _snapshot_key(item))

    # top5：同日同 国家×榜单 覆盖
    new_keys = {(_snapshot_key(item), str(item.get("date") or "")) for item in snapshots}
    top5_kept = []
    for snapshot in existing.get("top5") or []:
        if not isinstance(snapshot, Mapping):
            continue
        key = (_snapshot_key(snapshot), str(snapshot.get("date") or ""))
        if key in new_keys:
            continue
        top5_kept.append(snapshot)
    top5_kept.extend(_top5_snapshot(snapshot) for snapshot in snapshots)
    cutoff = today_value - timedelta(days=max(0, top5_days))
    top5 = [
        snapshot
        for snapshot in top5_kept
        if (store.parse_date(snapshot.get("date")) or today_value) >= cutoff
    ]
    top5.sort(key=lambda item: (item.get("date") or "", item.get("country") or "", item.get("kindId") or ""),
              reverse=True)

    # rankHistory：只记录 config 游戏；按日期去重；90 天裁剪
    history: Dict[str, Any] = {}
    for game_id, countries in (existing.get("rankHistory") or {}).items():
        if not isinstance(countries, dict):
            continue
        for country, kinds in countries.items():
            if not isinstance(kinds, dict):
                continue
            for kind_id, points in kinds.items():
                if isinstance(points, list):
                    trimmed = _trim_date_list(points, history_days, today_value)
                    if trimmed:
                        history.setdefault(game_id, {}).setdefault(country, {})[kind_id] = trimmed

    app_index = _app_index_by_country(games)
    for snapshot in snapshots:
        country = str(snapshot.get("country") or "")
        kind_id = str(snapshot.get("kindId") or "")
        app_to_game = app_index.get(country) or {}
        if not app_to_game:
            continue
        day = str(snapshot.get("date") or "")
        for entry in snapshot.get("entries") or []:
            app_id = str(entry.get("appId") or "")
            game_id = app_to_game.get(app_id)
            if not game_id:
                continue
            points = history.setdefault(game_id, {}).setdefault(country, {}).setdefault(kind_id, [])
            points[:] = [point for point in points if point and point[0] != day]
            points.append([day, entry.get("rank")])
            points.sort(key=lambda point: point[0])
            history[game_id][country][kind_id] = _trim_date_list(points, history_days, today_value)

    return {
        "latest": latest,
        "top5": top5[: 90 * 12] if top5 else [],
        "rankHistory": history,
        "updatedAt": updated_at,
    }


def _app_index_by_country(games: Iterable[Mapping[str, Any]]) -> Dict[str, Dict[str, str]]:
    index: Dict[str, Dict[str, str]] = {}
    for game in games or []:
        game_id = game.get("id")
        stores = game.get("stores") or {}
        if not game_id or not isinstance(stores, dict):
            continue
        for store_key, app_id in stores.items():
            if app_id:
                index.setdefault(str(store_key), {})[str(app_id)] = str(game_id)
    return index


def chart_state_from_snapshots(previous: Mapping[str, Any], snapshots: Iterable[Mapping[str, Any]],
                               today_value: Optional[date] = None,
                               updated_at: Optional[str] = None) -> dict:
    """生成本次 chart_state（供 alerts 比较）；失败/缺失的 国家×榜单 保留上一次。"""
    today_value = today_value or store.today()
    state = {
        "date": (today_value.isoformat()),
        "ranks": {},
        "updatedAt": updated_at or store.now_iso(),
    }
    if isinstance(previous, Mapping) and isinstance(previous.get("ranks"), dict):
        for country, kinds in previous["ranks"].items():
            if isinstance(kinds, dict):
                state["ranks"][country] = {
                    kind_id: dict(ranks) for kind_id, ranks in kinds.items() if isinstance(ranks, dict)
                }
    snapshots = [item for item in snapshots or [] if isinstance(item, Mapping)]
    if not snapshots:
        # 本次没有成功快照：保持旧状态，日期也保持旧日期
        return dict(previous) if isinstance(previous, Mapping) and previous else state
    for snapshot in snapshots:
        country = str(snapshot.get("country") or "")
        kind_id = str(snapshot.get("kindId") or "")
        ranks = {
            str(entry.get("appId") or ""): entry.get("rank")
            for entry in snapshot.get("entries") or []
            if entry.get("appId")
        }
        state["ranks"].setdefault(country, {})[kind_id] = ranks
    return state
