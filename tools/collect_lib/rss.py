"""RSS/Atom 线索抓取、严格关键词过滤与 drafts.json 合并。

要点（docs/COLLECTOR_BRIEF.md 第 5 节）：
- 读 config.feeds（enabled=true），宽容解析 RSS 2.0 与 Atom；
  对非法实体/控制字符做修复后再交给 ElementTree；
- 字段：title / link / pubDate（或 dc:date / published / updated）/ description，
  HTML 去标签、实体反转义、摘要截断 300 字；17173 无 pubDate 时从
  `/content/MMDDYYYY/` 形式的 URL 推日期；
- 关键词过滤：config.keywords + 游戏名 + 厂商名；17173 这类泛源（strict）
  必须命中“二合专有词/游戏名/厂商名”，只命中“消除/餐厅/合成”等泛词一律丢弃；
- URL 归一化（去 utm_*/fbclid/gclid 等追踪参数与 fragment）后按 URL 去重，
  与已有 drafts 去重；每轮最多 collector.maxDraftsPerRun 条；
- 写入 drafts.json：保留 120 天、最多 200 条；无 AI 时 aiStatus = "none"。
"""
from __future__ import annotations

import email.utils
import hashlib
import html
import re
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from . import http as http_mod
from . import store

DEFAULT_RETENTION_DAYS = 120
DEFAULT_MAX_DRAFTS = 200
DEFAULT_MAX_NEW_PER_RUN = 40
EXCERPT_LIMIT = 300

# 17173 这类泛流量源：只用“二合专有词 / 游戏名 / 厂商名”判定
STRICT_FEED_IDS = {"17173"}

# 二合专有词（不含“合成/合并/消除/餐厅”这类泛词，避免枪械合成、公司合并等噪音）
STRICT_KEYWORDS = (
    "merge-2", "merge2", "merge", "二合",
    "gossip harbor", "浪漫餐厅", "绯闻港口", "空格之境", "flambé", "flambe",
    "火辣餐厅", "merge cooking", "肥鹅", "肥鹅美食街", "梦幻消除战",
    "merge mansion", "travel town", "seaside escape", "merge gardens",
    "merge hotel", "merge county", "merge survival", "merge cafe",
    "merge restaurant", "tasty travels",
)

# 厂商名（跟踪游戏的发行商；大小写不敏感）
PUBLISHER_KEYWORDS = (
    "柠檬微趣", "microfun", "happibits", "playdayy", "天天玩家",
    "metacore", "moon active", "century games", "potato play",
    "csc mobi", "sticky hands", "futureplay", "豪腾", "喜势", "快游互动",
)

# 追踪参数（含 utm_* 前缀）
TRACKING_PARAMS = {
    "fbclid", "gclid", "dclid", "msclkid", "yclid", "spm", "scm",
    "from", "source", "ref", "refer", "share_token", "timestamp",
}

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_BARE_AMP_RE = re.compile(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9A-Fa-f]+);)")
_NAMED_ENTITY_RE = re.compile(r"&([A-Za-z][A-Za-z0-9]+);")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_URL_DATE_RE = re.compile(r"/content/(\d{2})(\d{2})(\d{4})/")


# -- 基础清洗 -------------------------------------------------------------
def sanitize_xml(raw: Any) -> str:
    """修复非法控制字符与未转义 & / HTML 命名实体，返回可解析文本。"""
    if isinstance(raw, bytes):
        text = raw.decode("utf-8", errors="replace")
    else:
        text = str(raw)
    text = text.lstrip("\ufeff")
    text = _CONTROL_RE.sub("", text)

    def _named(match: re.Match) -> str:
        name = match.group(1)
        if name in ("amp", "lt", "gt", "quot", "apos"):
            return match.group(0)
        return html.unescape(match.group(0))

    text = _NAMED_ENTITY_RE.sub(_named, text)
    text = _BARE_AMP_RE.sub("&amp;", text)
    return text


def html_to_text(raw: Any, limit: int = 0) -> str:
    """去 HTML 标签、反转义实体、压缩空白；limit>0 时截断。"""
    if raw is None:
        return ""
    text = str(raw)
    text = _HTML_TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    text = _WS_RE.sub(" ", text).strip()
    if limit and len(text) > limit:
        text = text[: max(0, limit - 1)].rstrip() + "…"
    return text


def normalize_url(raw: Any) -> str:
    """URL 归一化：小写 scheme/host、去 fragment、去 utm_* 等追踪参数、去尾斜杠。"""
    text = html.unescape(str(raw or "")).strip()
    if not text:
        return ""
    try:
        parts = urlsplit(text)
    except ValueError:
        return ""
    if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
        return ""
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=False)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMS
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), "")
    )


def parse_date_value(raw: Any) -> str:
    """解析 RFC822 / ISO 日期为 YYYY-MM-DD；失败返回空串。"""
    text = str(raw or "").strip()
    if not text:
        return ""
    try:
        parsed = email.utils.parsedate_to_datetime(text)
        if parsed is not None:
            return parsed.date().isoformat()
    except (TypeError, ValueError, IndexError):
        pass
    candidate = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(candidate).date().isoformat()
    except ValueError:
        pass
    match = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", text)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()
        except ValueError:
            return ""
    return ""


def date_from_url(url: str) -> str:
    """从 17173 的 /content/MMDDYYYY/ 路径推断日期。"""
    match = _URL_DATE_RE.search(url or "")
    if not match:
        return ""
    month, day, year = match.group(1), match.group(2), match.group(3)
    try:
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return ""


# -- 关键词 ---------------------------------------------------------------
def _keyword_hit(haystack: str, keyword: str) -> bool:
    """中文用子串；英文/数字词加边界，避免 emergency 命中 merge。"""
    keyword = keyword.strip().lower()
    if not keyword:
        return False
    if re.fullmatch(r"[a-z0-9 .&'\-]+", keyword):
        pattern = r"(?<![a-z0-9])" + re.escape(keyword).replace(r"\ ", r"\s+") + r"(?![a-z0-9])"
        return re.search(pattern, haystack) is not None
    return keyword in haystack


def keyword_hits(text: str, keywords: Iterable[str]) -> List[str]:
    haystack = (text or "").lower()
    hits = []
    for keyword in keywords:
        if keyword and _keyword_hit(haystack, keyword) and keyword not in hits:
            hits.append(keyword)
    return hits


def strong_keywords(games: Iterable[Mapping[str, Any]] = ()) -> List[str]:
    keywords = list(STRICT_KEYWORDS) + list(PUBLISHER_KEYWORDS)
    for game in games or []:
        for field in ("name", "nameZh"):
            value = str(game.get(field) or "").strip().lower()
            if value:
                keywords.append(value)
    # 去重且保持顺序
    seen = set()
    result = []
    for keyword in keywords:
        if keyword and keyword not in seen:
            seen.add(keyword)
            result.append(keyword)
    return result


def general_keywords(config: Mapping[str, Any], games: Iterable[Mapping[str, Any]] = ()) -> List[str]:
    keywords = list(config.get("keywords") or []) + strong_keywords(games)
    seen = set()
    result = []
    for keyword in keywords:
        key = str(keyword).strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return result


def is_relevant(title: str, excerpt: str, feed_cfg: Mapping[str, Any],
                config: Mapping[str, Any], games: Iterable[Mapping[str, Any]] = ()) -> bool:
    text = f"{title} {excerpt}"
    feed_id = str(feed_cfg.get("id") or "")
    strict = bool(feed_cfg.get("strict")) or feed_id in STRICT_FEED_IDS
    if strict:
        return bool(keyword_hits(text, strong_keywords(games)))
    return bool(keyword_hits(text, general_keywords(config, games)))


# -- 解析 -----------------------------------------------------------------
def _local(tag: Any) -> str:
    return str(tag).rsplit("}", 1)[-1].lower()


def _element_text(element: Any) -> str:
    return "".join(element.itertext()).strip()


def parse_feed(raw: Any) -> List[dict]:
    """解析 RSS/Atom 文本，返回 [{title, link, date, description}]（按原文顺序）。"""
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(sanitize_xml(raw))
    except ET.ParseError:
        return []
    items: List[dict] = []
    for element in root.iter():
        if _local(element.tag) not in ("item", "entry"):
            continue
        fields: Dict[str, str] = {}
        for child in element:
            name = _local(child.tag)
            if name == "link":
                href = child.get("href") or _element_text(child)
                if href and "link" not in fields:
                    fields["link"] = href
            elif name == "title":
                fields.setdefault("title", _element_text(child))
            elif name in ("description", "summary"):
                fields.setdefault("description", _element_text(child))
            elif name in ("content", "encoded"):
                fields.setdefault("content", _element_text(child))
            elif name in ("pubdate", "date", "published", "updated"):
                fields.setdefault("date", _element_text(child))
        items.append({
            "title": html_to_text(fields.get("title", "")),
            "link": html.unescape(fields.get("link", "")).strip(),
            "date": fields.get("date", ""),
            "description": fields.get("description") or fields.get("content") or "",
        })
    return items


def make_draft(feed_cfg: Mapping[str, Any], item: Mapping[str, Any], today_value: date,
               fetched_at: Optional[str] = None) -> Optional[dict]:
    """把解析后的 feed item 转成 drafts.json 结构；非法条目返回 None。"""
    title = html_to_text(item.get("title", ""))
    url = normalize_url(item.get("link", ""))
    if not title or not url:
        return None
    published = parse_date_value(item.get("date", "")) or date_from_url(url) or today_value.isoformat()
    excerpt = html_to_text(item.get("description", ""), EXCERPT_LIMIT)
    source_id = str(feed_cfg.get("id") or "rss")
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    return {
        "id": f"draft-{today_value.strftime('%Y%m%d')}-{source_id}-{digest}",
        "title": title,
        "excerpt": excerpt,
        "url": url,
        "sourceId": source_id,
        "publishedAt": published,
        "lang": str(feed_cfg.get("lang") or "zh"),
        "fetchedAt": fetched_at or store.now_iso(),
        "aiStatus": "none",
        "relevance": None,
    }


# -- 抓取 -----------------------------------------------------------------
def fetch_feed(client: http_mod.HttpClient, feed_cfg: Mapping[str, Any],
               config: Mapping[str, Any], games: Iterable[Mapping[str, Any]],
               today_value: Optional[date] = None,
               fetched_at: Optional[str] = None,
               logger: Optional[Callable[[str], None]] = None) -> Tuple[List[dict], dict]:
    """抓取并过滤单个 feed；返回 (drafts, status_entry)。"""
    log = logger or (lambda _message: None)
    today_value = today_value or store.today()
    feed_id = str(feed_cfg.get("id") or "unknown")
    source_key = f"rss_{feed_id}"
    try:
        raw = client.get_text(str(feed_cfg.get("url") or ""))
        items = parse_feed(raw)
        drafts = []
        seen_urls = set()
        for item in items:
            if not is_relevant(item.get("title", ""), html_to_text(item.get("description", ""), 500),
                               feed_cfg, config, games):
                continue
            draft = make_draft(feed_cfg, item, today_value, fetched_at)
            if draft and draft["url"] not in seen_urls:
                seen_urls.add(draft["url"])
                drafts.append(draft)
        log(f"  RSS {feed_id}: {len(items)} 条原始，命中 {len(drafts)} 条")
        return drafts, store.status_entry(True, items=len(drafts))
    except Exception as exc:  # 单源失败不影响其他源
        log(f"  RSS {feed_id} 失败：{type(exc).__name__}: {exc}")
        return [], store.status_entry(False, items=0, error=f"{type(exc).__name__}: {exc}")


def fetch_drafts(client: http_mod.HttpClient, config: Mapping[str, Any],
                 games: Iterable[Mapping[str, Any]],
                 logger: Optional[Callable[[str], None]] = None,
                 today_value: Optional[date] = None,
                 fetched_at: Optional[str] = None) -> Tuple[List[dict], Dict[str, dict]]:
    """抓取 config.feeds 中所有 enabled=true 的源；返回 (drafts, source_status)。"""
    log = logger or (lambda _message: None)
    all_drafts: List[dict] = []
    statuses: Dict[str, dict] = {}
    for feed_cfg in config.get("feeds") or []:
        if not isinstance(feed_cfg, Mapping) or not feed_cfg.get("enabled", True):
            continue
        feed_id = str(feed_cfg.get("id") or "unknown")
        drafts, status = fetch_feed(client, feed_cfg, config, games, today_value, fetched_at, logger)
        all_drafts.extend(drafts)
        statuses[f"rss_{feed_id}"] = status
    return all_drafts, statuses


# -- 合并 -----------------------------------------------------------------
def _draft_date(draft: Mapping[str, Any]) -> str:
    return str(draft.get("publishedAt") or "")


def merge_drafts(existing: Mapping[str, Any], new_drafts: Iterable[Mapping[str, Any]],
                 today_value: Optional[date] = None,
                 retention_days: int = DEFAULT_RETENTION_DAYS,
                 max_drafts: int = DEFAULT_MAX_DRAFTS,
                 max_new_per_run: int = DEFAULT_MAX_NEW_PER_RUN,
                 fetched_at: Optional[str] = None) -> dict:
    """合并 drafts：URL 去重、每轮新增上限、120 天保留、最多 200 条。"""
    today_value = today_value or store.today()
    existing_list = []
    if isinstance(existing, Mapping) and isinstance(existing.get("drafts"), list):
        existing_list = [item for item in existing["drafts"] if isinstance(item, Mapping)]
    by_url: Dict[str, dict] = {}
    for draft in existing_list:
        url = normalize_url(draft.get("url", ""))
        if url and url not in by_url:
            by_url[url] = dict(draft)
    added = 0
    candidates = sorted(
        (dict(item) for item in new_drafts if isinstance(item, Mapping)),
        key=lambda item: (_draft_date(item), str(item.get("id") or "")),
        reverse=True,
    )
    for draft in candidates:
        url = normalize_url(draft.get("url", ""))
        if not url or url in by_url:
            continue
        if added >= max(0, max_new_per_run):
            break
        by_url[url] = draft
        added += 1
    cutoff = today_value - timedelta(days=max(0, retention_days))
    kept = []
    for draft in by_url.values():
        parsed = store.parse_date(draft.get("publishedAt"))
        if parsed is None or parsed >= cutoff:
            kept.append(draft)
    kept.sort(key=lambda item: (_draft_date(item), str(item.get("id") or "")), reverse=True)
    return {"drafts": kept[:max(0, max_drafts)], "updatedAt": fetched_at or store.now_iso()}


def draft_urls(drafts: Iterable[Mapping[str, Any]]) -> List[str]:
    return [normalize_url(item.get("url", "")) for item in drafts or [] if item.get("url")]


def summarize_drafts(payload: Mapping[str, Any]) -> dict:
    drafts = payload.get("drafts") if isinstance(payload, Mapping) else []
    drafts = drafts if isinstance(drafts, list) else []
    by_source: Dict[str, int] = {}
    for draft in drafts:
        source = str(draft.get("sourceId") or "?")
        by_source[source] = by_source.get(source, 0) + 1
    return {"total": len(drafts), "bySource": by_source}


def drafts_json_path():
    return store.auto_path("drafts.json")
