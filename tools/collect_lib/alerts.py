"""告警规则与去重（docs/COLLECTOR_BRIEF.md 第 7 节）。

规则：
1. top5：跟踪游戏进入任一国家 × Puzzle/Casual 畅销前 5（首次或重新进入）；
2. rank-jump：跟踪游戏任一榜单日环比上升 ≥15 名；
3. version：跟踪游戏新版本 release notes 命中活动/赛季/通行证/新章节/联动等关键词；
4. suspect-hit：未知应用进入 Puzzle/Casual 畅销前 10 且名称/厂商命中二合强关键词（无 AI 时的保守判定）。

去重：
- 首次运行没有 chart_state 时只建立基线，不告警；
- 同一份 chart_state 同日重复运行不重复告警（同日快照覆盖）；
- top5 连续在榜期间不重复报，掉出前 5 后重新进入才再报；
- 所有新告警再经 data/auto/state/alert_state.json 的 id 去重；
- alerts.json 保留 180 天、最多 300 条。
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

from . import store

TOP5_KINDS = {"puzzle-grossing", "casual-grossing"}
NEW_ENTRY_KINDS = {"puzzle-grossing", "casual-grossing"}
TOP5_RANK = 5
NEW_ENTRY_RANK = 10
RANK_JUMP_DELTA = 15
RETENTION_DAYS = 180
MAX_ALERTS = 300

# 未知应用判定“疑似二合”的强关键词（宁缺毋滥，避免“消除/餐厅”泛词噪音）
STRONG_KEYWORDS = (
    "merge", "merge-2", "merge2", "二合", "合成", "合并",
    "gossip harbor", "浪漫餐厅", "空格之境", "flambé", "flambe",
    "肥鹅", "梦幻消除战", "merge mansion", "travel town", "seaside escape",
    "mansion", "merge county", "merge hotel", "merge survival", "merge cafe",
    "merge restaurant", "tasty travels", "merge gardens",
)

# 版本更新说明命中活动/赛季类关键词
VERSION_KEYWORDS = (
    "活动", "赛季", "通行证", "新章节", "章节", "联动", "节日", "限时",
    "event", "season", "pass", "battle pass", "chapter", "crossover",
    "collab", "festival", "update", "新版本", "新玩法", "挑战",
)

STORE_LABELS = {"cn": "中国区", "us": "美区", "jp": "日区", "kr": "韩区", "hk": "港区", "tw": "台区"}


# -- 小工具 ---------------------------------------------------------------
def source_url(country: str, app_id: Any) -> str:
    return f"https://apps.apple.com/{country}/app/id{app_id}"


def _compact_date(value: str) -> str:
    return str(value or "").replace("-", "")


def _as_rank(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _game_index_by_country_app(games: Iterable[Mapping[str, Any]]) -> Dict[Tuple[str, str], Mapping[str, Any]]:
    index: Dict[Tuple[str, str], Mapping[str, Any]] = {}
    for game in games or []:
        stores = game.get("stores") or {}
        if not isinstance(stores, dict):
            continue
        for store_key, app_id in stores.items():
            if app_id:
                index[(str(store_key), str(app_id))] = game
    return index


def _matches_strong_keywords(name: str, publisher: str) -> bool:
    haystack = f"{name or ''} {publisher or ''}".lower()
    return any(keyword in haystack for keyword in STRONG_KEYWORDS)


def _matches_version_keywords(notes: str) -> bool:
    haystack = (notes or "").lower()
    return any(keyword in haystack for keyword in VERSION_KEYWORDS)


def _alert_id(kind: str, date_str: str, country: str, kind_id: str, subject: str) -> str:
    return f"alert-{_compact_date(date_str)}-{country}-{kind_id}-{subject}-{kind}"


def _chart_alert(kind: str, date_str: str, snapshot: Mapping[str, Any], entry: Mapping[str, Any],
                 rank: int, prev_rank: Optional[int], confidence: str, summary: str,
                 game: Optional[Mapping[str, Any]] = None) -> dict:
    country = str(snapshot.get("country") or "")
    app_id = str(entry.get("appId") or "")
    game_id = str(game.get("id")) if game and game.get("id") else None
    alert = {
        "id": _alert_id(kind, date_str, country, str(snapshot.get("kindId") or ""),
                        game_id or f"app-{app_id}"),
        "date": date_str,
        "type": kind,
        "country": country,
        "kindId": snapshot.get("kindId"),
        "appId": app_id,
        "name": entry.get("name") or "",
        "rank": rank,
        "prevRank": prev_rank,
        "confidence": confidence,
        "summary": summary,
        "sourceUrl": source_url(country, app_id),
    }
    if game_id:
        alert["gameId"] = game_id
    if entry.get("publisher"):
        alert["publisher"] = entry.get("publisher")
    return alert


# -- 榜单告警 -------------------------------------------------------------
def detect_chart_alerts(previous_state: Optional[Mapping[str, Any]],
                        snapshots: Iterable[Mapping[str, Any]],
                        games: Iterable[Mapping[str, Any]],
                        date_str: Optional[str] = None,
                        logger: Optional[Callable[[str], None]] = None) -> List[dict]:
    """基于上一份 chart_state 生成本轮榜单告警（无 state 时只建基线）。"""
    log = logger or (lambda _message: None)
    date_str = date_str or store.today_str()
    if not isinstance(previous_state, Mapping):
        return []
    prev_ranks = previous_state.get("ranks")
    if not isinstance(prev_ranks, dict) or not prev_ranks:
        log("  告警：无上一份 chart_state，本轮只建立基线")
        return []
    if str(previous_state.get("date") or "") == date_str:
        log("  告警：同日已有快照，跳过重复比对")
        return []

    game_index = _game_index_by_country_app(games)
    alerts: List[dict] = []
    for snapshot in snapshots or []:
        if not isinstance(snapshot, Mapping):
            continue
        country = str(snapshot.get("country") or "")
        kind_id = str(snapshot.get("kindId") or "")
        label = str(snapshot.get("label") or kind_id)
        prev_kind = (prev_ranks.get(country) or {}).get(kind_id) or {}
        if not isinstance(prev_kind, dict):
            prev_kind = {}
        for entry in snapshot.get("entries") or []:
            rank = _as_rank(entry.get("rank"))
            app_id = str(entry.get("appId") or "")
            if rank is None or not app_id:
                continue
            prev_rank = _as_rank(prev_kind.get(app_id))
            game = game_index.get((country, app_id))
            if game:
                game_name = str(game.get("nameZh") or game.get("name") or app_id)
                if kind_id in TOP5_KINDS and rank <= TOP5_RANK and (prev_rank is None or prev_rank > TOP5_RANK):
                    change = f"（上次第 {prev_rank}）" if prev_rank else "（新进前 5）"
                    alerts.append(_chart_alert(
                        "top5", date_str, snapshot, entry, rank, prev_rank, "high",
                        f"{game_name} 进入{STORE_LABELS.get(country, country)} {label}前 5，当前第 {rank}{change}。",
                        game,
                    ))
                if prev_rank is not None and prev_rank - rank >= RANK_JUMP_DELTA:
                    alerts.append(_chart_alert(
                        "rank-jump", date_str, snapshot, entry, rank, prev_rank, "medium",
                        f"{game_name} 在{STORE_LABELS.get(country, country)} {label}上升 {prev_rank - rank} 名，第 {prev_rank} → 第 {rank}。",
                        game,
                    ))
            elif kind_id in NEW_ENTRY_KINDS and rank <= NEW_ENTRY_RANK and (
                prev_rank is None or prev_rank > NEW_ENTRY_RANK
            ):
                name = str(entry.get("name") or "")
                publisher = str(entry.get("publisher") or "")
                if _matches_strong_keywords(name, publisher):
                    alerts.append(_chart_alert(
                        "suspect-hit", date_str, snapshot, entry, rank, prev_rank, "low",
                        f"疑似二合新面孔：{name}（{publisher or '厂商未知'}）进入{STORE_LABELS.get(country, country)} {label}前 10，第 {rank}，待人工/AI 核实。",
                    ))
    return _dedupe_alerts(alerts)


# -- 版本告警 -------------------------------------------------------------
def _version_keys(versions: Iterable[Mapping[str, Any]]) -> Tuple[set, set]:
    ids, group_keys = set(), set()
    for record in versions or []:
        if not isinstance(record, Mapping):
            continue
        ids.add(str(record.get("id") or ""))
        group_keys.add((
            str(record.get("gameId") or ""),
            str(record.get("store") or ""),
            str(record.get("version") or ""),
        ))
    return ids, group_keys


def detect_version_alerts(previous_versions: Iterable[Mapping[str, Any]],
                          current_versions: Iterable[Mapping[str, Any]],
                          games: Iterable[Mapping[str, Any]],
                          date_str: Optional[str] = None) -> List[dict]:
    """新版本 + 关键词 → version 告警；首次运行（无旧版本）只建基线。"""
    date_str = date_str or store.today_str()
    previous_versions = list(previous_versions or [])
    if not previous_versions:
        return []
    prev_ids, prev_keys = _version_keys(previous_versions)
    games_map = {str(game.get("id")): game for game in games or [] if game.get("id")}
    alerts: List[dict] = []
    for record in current_versions or []:
        if not isinstance(record, Mapping):
            continue
        if str(record.get("id") or "") in prev_ids:
            continue
        group_key = (
            str(record.get("gameId") or ""),
            str(record.get("store") or ""),
            str(record.get("version") or ""),
        )
        if group_key in prev_keys:
            continue  # 同一版本更换发布日期不算新版本
        notes = str(record.get("notes") or "")
        if not _matches_version_keywords(notes):
            continue
        game_id = str(record.get("gameId") or "")
        store_key = str(record.get("store") or "")
        game = games_map.get(game_id) or {}
        game_name = str(game.get("nameZh") or game.get("name") or game_id)
        app_id = str((game.get("stores") or {}).get(store_key) or "")
        keywords = [keyword for keyword in VERSION_KEYWORDS if keyword.lower() in notes.lower()][:3]
        version = str(record.get("version") or "")
        alert = {
            "id": _alert_id("version", date_str, store_key, "app", f"{game_id}-{version}"),
            "date": date_str,
            "type": "version",
            "country": store_key,
            "gameId": game_id,
            "appId": app_id,
            "name": game_name,
            "version": version,
            "rank": None,
            "prevRank": None,
            "confidence": "medium",
            "summary": (
                f"{game_name} 发布新版本 {version}（{STORE_LABELS.get(store_key, store_key)}），"
                f"更新说明命中：{'、'.join(keywords)}。"
            ),
            "sourceUrl": source_url(store_key, app_id or "0"),
        }
        alerts.append(alert)
    return _dedupe_alerts(alerts)


# -- 合并 / 去重 / 状态 ---------------------------------------------------
def _dedupe_alerts(alerts: Iterable[Mapping[str, Any]]) -> List[dict]:
    seen = set()
    result = []
    for alert in alerts or []:
        alert_id = str((alert or {}).get("id") or "")
        if not alert_id or alert_id in seen:
            continue
        seen.add(alert_id)
        result.append(dict(alert))
    return result


def filter_new_alerts(alerts: Iterable[Mapping[str, Any]],
                      alert_state: Optional[Mapping[str, Any]]) -> List[dict]:
    """用 alert_state 里的已报 id 过滤重复告警。"""
    reported = {}
    if isinstance(alert_state, Mapping):
        reported = alert_state.get("reported") or {}
    if not isinstance(reported, dict):
        reported = {}
    return [dict(alert) for alert in alerts or []
            if str((alert or {}).get("id") or "") not in reported]


def update_alert_state(alert_state: Optional[Mapping[str, Any]], alerts: Iterable[Mapping[str, Any]],
                       today_value: Optional[date] = None,
                       retention_days: int = RETENTION_DAYS) -> dict:
    """把本轮告警 id 记入 state，并清理过期项。"""
    today_value = today_value or store.today()
    reported: Dict[str, str] = {}
    if isinstance(alert_state, Mapping) and isinstance(alert_state.get("reported"), dict):
        reported = {str(key): str(value) for key, value in alert_state["reported"].items()}
    for alert in alerts or []:
        alert_id = str((alert or {}).get("id") or "")
        if alert_id:
            reported[alert_id] = str((alert or {}).get("date") or today_value.isoformat())
    cutoff = today_value - timedelta(days=max(0, retention_days))
    pruned = {}
    for alert_id, reported_date in reported.items():
        parsed = store.parse_date(reported_date)
        if parsed is None or parsed >= cutoff:
            pruned[alert_id] = reported_date
    return {"reported": pruned, "updatedAt": store.now_iso()}


def merge_alerts(existing: Mapping[str, Any], new_alerts: Iterable[Mapping[str, Any]],
                 today_value: Optional[date] = None,
                 retention_days: int = RETENTION_DAYS,
                 max_alerts: int = MAX_ALERTS,
                 updated_at: Optional[str] = None) -> dict:
    """合并告警：按 id 去重、180 天保留、最多 300 条（保留最新）。"""
    today_value = today_value or store.today()
    updated_at = updated_at or store.now_iso()
    cutoff = today_value - timedelta(days=max(0, retention_days))
    merged: Dict[str, dict] = {}
    sources = list((existing or {}).get("alerts") or []) + list(new_alerts or [])
    for alert in sources:
        if not isinstance(alert, Mapping):
            continue
        alert_id = str(alert.get("id") or "")
        if not alert_id or alert_id in merged:
            continue
        merged[alert_id] = {key: value for key, value in alert.items() if not str(key).startswith("_")}
    kept = []
    for alert in merged.values():
        parsed = store.parse_date(alert.get("date"))
        if parsed is None or parsed >= cutoff:
            kept.append(alert)
    kept.sort(key=lambda item: (item.get("date") or "", item.get("id") or ""), reverse=True)
    return {"alerts": kept[:max_alerts], "updatedAt": updated_at}
