"""App Store 版本抓取（iTunes lookup）与版本记录合并。

接口：``https://itunes.apple.com/lookup?id=a,b,c&country=cn|us&lang=zh_cn|en_us``
- 每国一次批量请求（lookup 支持逗号批量），减少请求数；
- 解析 version / currentVersionReleaseDate / releaseNotes / averageUserRating /
  userRatingCount / trackViewUrl / price / genres；
- 版本 id：``version-<gameId>-<store>-<version>-<releasedAt>``；
- 同一游戏/商店保留最近 20 版，notes 截断 2000 字，按 releasedAt 倒序。
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

from . import http as http_mod
from . import store

LOOKUP_URL = "https://itunes.apple.com/lookup"
APP_URL = "https://apps.apple.com/{store}/app/id{app_id}"
VERSIONS_PER_GROUP = 20
NOTES_LIMIT = 2000
STORE_LANGS = {"cn": "zh_cn", "us": "en_us", "jp": "ja_jp", "kr": "ko_kr", "hk": "zh_hk", "tw": "zh_tw"}
_SLUG_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _slug(text: Any) -> str:
    cleaned = _SLUG_SAFE.sub("-", str(text or "").strip()).strip("-")
    return cleaned or "na"


# -- 游戏 / appId 索引 ----------------------------------------------------
def game_store_index(games: Iterable[Mapping[str, Any]]) -> Dict[str, Dict[str, str]]:
    """返回 {store: {appId: gameId}}。"""
    index: Dict[str, Dict[str, str]] = {}
    for game in games or []:
        game_id = game.get("id")
        stores = game.get("stores") or {}
        if not game_id or not isinstance(stores, dict):
            continue
        for store_key, app_id in stores.items():
            if not app_id:
                continue
            index.setdefault(store_key, {})[str(app_id)] = game_id
    return index


def games_by_id(games: Iterable[Mapping[str, Any]]) -> Dict[str, Mapping[str, Any]]:
    return {str(game.get("id")): game for game in games or [] if game.get("id")}


# -- URL 与解析 -----------------------------------------------------------
def lookup_url(app_ids: Iterable[str], country: str, lang: Optional[str] = None) -> str:
    ids = ",".join(str(app_id).strip() for app_id in app_ids if str(app_id).strip())
    language = lang or STORE_LANGS.get(country, "en_us")
    return f"{LOOKUP_URL}?id={ids}&country={country}&lang={language}"


def parse_lookup(payload: Any) -> List[dict]:
    """从 lookup JSON 中取出 results 数组（过滤非对象）。"""
    if isinstance(payload, dict):
        results = payload.get("results")
        if isinstance(results, list):
            return [item for item in results if isinstance(item, dict)]
    return []


def _release_date(result: Mapping[str, Any]) -> str:
    raw = str(result.get("currentVersionReleaseDate") or result.get("releaseDate") or "")
    parsed = store.parse_date(raw)
    if parsed:
        return parsed.isoformat()
    return ""


def make_version_record(game_id: str, store_key: str, result: Mapping[str, Any],
                        fetched_at: Optional[str] = None) -> dict:
    """把一条 lookup result 转成 versions.json 记录。"""
    version = str(result.get("version") or result.get("bundleVersion") or "").strip() or "unknown"
    released_at = _release_date(result)
    app_id = str(result.get("trackId") or "").strip()
    record_id = f"version-{game_id}-{store_key}-{_slug(version)}-{released_at or 'unknown'}"
    notes = store.truncate(result.get("releaseNotes") or "", NOTES_LIMIT)
    track_url = str(result.get("trackViewUrl") or "").strip()
    if not track_url and app_id:
        track_url = APP_URL.format(store=store_key, app_id=app_id)
    rating_count = result.get("userRatingCount")
    average_rating = result.get("averageUserRating")
    return {
        "id": record_id,
        "gameId": game_id,
        "store": store_key,
        "version": version,
        "releasedAt": released_at,
        "notes": notes,
        "notesUrl": track_url,
        "ratingCount": int(rating_count) if isinstance(rating_count, (int, float)) else None,
        "averageRating": float(average_rating) if isinstance(average_rating, (int, float)) else None,
        "highlights": [],
        "fetchedAt": fetched_at or store.now_iso(),
    }


def records_from_lookup(payload: Any, store_key: str,
                        app_to_game: Mapping[str, str],
                        fetched_at: Optional[str] = None) -> List[dict]:
    records = []
    for result in parse_lookup(payload):
        app_id = str(result.get("trackId") or "")
        game_id = app_to_game.get(app_id)
        if not game_id:
            continue
        records.append(make_version_record(game_id, store_key, result, fetched_at))
    return records


# -- 合并 / 去重 / 裁剪 ---------------------------------------------------
def _group_key(record: Mapping[str, Any]) -> Tuple[str, str]:
    return str(record.get("gameId") or ""), str(record.get("store") or "")


def merge_versions(existing: Iterable[Mapping[str, Any]], incoming: Iterable[Mapping[str, Any]],
                   fetched_at: Optional[str] = None,
                   keep_per_group: int = VERSIONS_PER_GROUP) -> List[dict]:
    """合并版本记录。

    - 同一 (gameId, store, version)：以最新 releasedAt 为准（视为同一版本更新），
      不重复追加；同日期则保留旧记录，仅补充评分/notes（notes 为空时）。
    - 每个 (gameId, store) 只保留最近 keep_per_group 个版本；
    - 最终按 releasedAt 倒序（同日期按 gameId/store/version）。
    """
    merged: Dict[Tuple[str, str, str], dict] = {}
    for record in list(existing or []) + list(incoming or []):
        if not isinstance(record, Mapping):
            continue
        game_id, store_key = _group_key(record)
        version = str(record.get("version") or "")
        if not game_id or not store_key or not version:
            continue
        key = (game_id, store_key, version)
        if key not in merged:
            merged[key] = {k: v for k, v in record.items() if not str(k).startswith("_")}
            continue
        current = merged[key]
        current_date = store.parse_date(current.get("releasedAt"))
        new_date = store.parse_date(record.get("releasedAt"))
        candidate = {k: v for k, v in record.items() if not str(k).startswith("_")}
        if new_date and (current_date is None or new_date > current_date):
            # 同一版本不同日期视为更新：沿用旧 id 的 highlights，其余以新记录为准
            if not candidate.get("highlights") and current.get("highlights"):
                candidate["highlights"] = current["highlights"]
            merged[key] = candidate
        else:
            # 同 id 不重复追加；补全旧记录缺失的说明与评分
            if not current.get("notes") and candidate.get("notes"):
                current["notes"] = candidate["notes"]
            for field in ("ratingCount", "averageRating", "notesUrl"):
                if current.get(field) in (None, "", 0) and candidate.get(field) not in (None, "", 0):
                    current[field] = candidate[field]
            if not current.get("fetchedAt"):
                current["fetchedAt"] = candidate.get("fetchedAt") or fetched_at or store.now_iso()

    # 每组按发布日期倒序保留前 N 个
    groups: Dict[Tuple[str, str], List[dict]] = {}
    for record in merged.values():
        groups.setdefault(_group_key(record), []).append(record)
    trimmed: List[dict] = []
    for group_records in groups.values():
        group_records.sort(
            key=lambda item: (
                item.get("releasedAt") or "",
                item.get("fetchedAt") or "",
                item.get("version") or "",
            ),
            reverse=True,
        )
        trimmed.extend(group_records[: max(1, keep_per_group)])

    trimmed.sort(
        key=lambda item: (
            item.get("releasedAt") or "",
            item.get("gameId") or "",
            item.get("store") or "",
            item.get("version") or "",
        ),
        reverse=True,
    )
    return trimmed


# -- 抓取入口 -------------------------------------------------------------
def fetch_versions(client: http_mod.HttpClient,
                   games: Iterable[Mapping[str, Any]],
                   logger: Optional[Callable[[str], None]] = None) -> Tuple[List[dict], Dict[str, dict]]:
    """按商店批量抓取版本；单商店失败隔离。"""
    log = logger or (lambda _message: None)
    index = game_store_index(games)
    fetched_at = store.now_iso()
    records: List[dict] = []
    statuses: Dict[str, dict] = {}
    for store_key, app_to_game in index.items():
        if not app_to_game:
            continue
        source_key = f"itunes_lookup_{store_key}"
        app_ids = sorted(app_to_game.keys())
        url = lookup_url(app_ids, store_key)
        try:
            payload = client.get_json(url)
            batch = records_from_lookup(payload, store_key, app_to_game, fetched_at)
            records.extend(batch)
            # lookup 对部分无效 id 会静默省略：记录缺失数量便于排查
            missing = len(app_ids) - len(batch)
            note = f"{len(batch)}/{len(app_ids)} 个 appId 返回"
            if missing > 0:
                note += f"，缺少 {missing} 个（可能下架/区域不符）"
            statuses[source_key] = store.status_entry(True, items=len(batch), error="" if missing == 0 else note)
            log(f"  版本 {store_key}: {len(batch)} 条（{note}）")
        except Exception as exc:  # 单源失败不阻断
            statuses[source_key] = store.status_entry(False, items=0, error=f"{type(exc).__name__}: {exc}")
            log(f"  版本 {store_key} 失败：{type(exc).__name__}: {exc}")
    return records, statuses


def version_source_url(store_key: str, app_id: str) -> str:
    return APP_URL.format(store=store_key, app_id=app_id)
