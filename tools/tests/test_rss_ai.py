"""RSS + AI 测试（stdlib unittest，全部 mock，不联网）。

覆盖：RSS/Atom 解析、HTML 清洗、日期解析/URL 推断、严格关键词过滤、
URL 归一化与去重、每轮上限、120 天/200 条保留；AI key 解析、批量调用、
缓存命中、失败降级、Item schema 构造、items-auto 合并。
"""
from __future__ import annotations

import contextlib
import json
import os
import shutil
import unittest
import uuid
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

from collect_lib import ai as ai_mod
from collect_lib import rss

TODAY = date(2026, 11, 3)

CONFIG = {
    "keywords": ["merge", "二合", "合成", "消除", "餐厅", "cooking", "gossip harbor"],
    "games": [
        {"id": "gossip-harbor", "name": "Gossip Harbor", "stores": {"us": "1623318294"}},
        {"id": "merge-mansion", "name": "Merge Mansion", "stores": {"us": "1484442152"}},
    ],
    "ai": {
        "enabled": False,
        "model": "deepseek-chat",
        "maxCallsPerRun": 5,
        "maxItemsPerCall": 8,
        "relevanceThreshold": 0.7,
    },
}

RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel>
  <title>Test Feed</title>
  <item>
    <title>Gossip Harbor 推出全新限时活动</title>
    <link>https://example.com/a?utm_source=rss&amp;utm_medium=feed#top</link>
    <pubDate>Fri, 16 Oct 2026 06:28:34 +0000</pubDate>
    <description><![CDATA[<p>浪漫餐厅本周更新，<b>新增</b>赛季通行证。</p>]]></description>
  </item>
  <item>
    <title>某休闲消除游戏玩法分析（泛词）</title>
    <link>https://example.com/b</link>
    <dc:date>2026-10-15T09:00:00+08:00</dc:date>
    <description>只讲消除与餐厅经营，没有二合专有词。</description>
  </item>
  <item>
    <title>Emergency merge patch &nbsp; for a shooter</title>
    <link>https://example.com/c?spm=abc</link>
    <description>bare &amp; entity &unknownentity; test</description>
  </item>
  <item>
    <title>重复链接（utm 不同）</title>
    <link>https://example.com/a?utm_campaign=x</link>
    <description>Merge Mansion 相关内容</description>
  </item>
</channel>
</rss>
"""

ATOM_XML = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Feed</title>
  <entry>
    <title>Merge Mansion 新章节上线</title>
    <link href="https://example.org/atom-1?utm_medium=feed"/>
    <published>2026-10-20T08:00:00Z</published>
    <summary>新章节与联动活动。</summary>
  </entry>
  <entry>
    <title>无关科技新闻</title>
    <link href="https://example.org/atom-2"/>
    <updated>2026-10-21T08:00:00Z</updated>
    <summary>与游戏无关。</summary>
  </entry>
</feed>
"""


@contextlib.contextmanager
def workspace_tmpdir():
    root = Path(__file__).resolve().parent / "_tmp"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"case_{uuid.uuid4().hex[:10]}"
    path.mkdir(mode=0o755)
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


class TestRssParse(unittest.TestCase):
    def test_parse_rss_items(self):
        items = rss.parse_feed(RSS_XML)
        self.assertEqual(len(items), 4)
        self.assertEqual(items[0]["title"], "Gossip Harbor 推出全新限时活动")
        self.assertEqual(items[0]["link"], "https://example.com/a?utm_source=rss&utm_medium=feed#top")
        self.assertIn("Fri, 16 Oct 2026", items[0]["date"])
        self.assertIn("赛季通行证", items[0]["description"])
        # dc:date
        self.assertEqual(items[1]["date"], "2026-10-15T09:00:00+08:00")

    def test_parse_atom_entries(self):
        items = rss.parse_feed(ATOM_XML)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["title"], "Merge Mansion 新章节上线")
        self.assertEqual(items[0]["link"], "https://example.org/atom-1?utm_medium=feed")
        self.assertEqual(items[0]["date"], "2026-10-20T08:00:00Z")
        self.assertEqual(items[0]["description"], "新章节与联动活动。")

    def test_invalid_xml_returns_empty(self):
        self.assertEqual(rss.parse_feed("<not-xml"), [])
        self.assertEqual(rss.parse_feed(None), [])

    def test_sanitize_fixes_entities_and_controls(self):
        fixed = rss.sanitize_xml("<rss><title>a & b &nbsp; \x01c</title></rss>")
        self.assertIn("&amp;", fixed)
        self.assertNotIn("\x01", fixed)
        # 修复后可以正常解析
        self.assertEqual(rss.parse_feed("<rss><channel><item><title>a & b</title></item></channel></rss>"),
                         [{"title": "a & b", "link": "", "date": "", "description": ""}])

    def test_html_to_text(self):
        self.assertEqual(rss.html_to_text("<p>Hello&nbsp;<b>World</b> &amp; more</p>"), "Hello World & more")
        self.assertLessEqual(len(rss.html_to_text("x" * 500, 300)), 300)
        self.assertTrue(rss.html_to_text("x" * 500, 300).endswith("…"))
        self.assertEqual(rss.html_to_text(None), "")

    def test_normalize_url(self):
        self.assertEqual(
            rss.normalize_url("https://Example.COM/path/?utm_source=a&utm_medium=b&id=3#frag"),
            "https://example.com/path?id=3",
        )
        self.assertEqual(rss.normalize_url("https://example.com/path"), "https://example.com/path")
        self.assertEqual(rss.normalize_url("javascript:alert(1)"), "")
        self.assertEqual(rss.normalize_url(""), "")

    def test_parse_date_value(self):
        self.assertEqual(rss.parse_date_value("Fri, 16 Oct 2026 06:28:34 +0000"), "2026-10-16")
        self.assertEqual(rss.parse_date_value("2026-10-20T08:00:00Z"), "2026-10-20")
        self.assertEqual(rss.parse_date_value("2026年10月9日"), "2026-10-09")
        self.assertEqual(rss.parse_date_value("garbage"), "")

    def test_date_from_17173_url(self):
        self.assertEqual(
            rss.date_from_url("http://news.17173.com/content/11032026/120358043.shtml"), "2026-11-03"
        )
        self.assertEqual(rss.date_from_url("https://example.com/x"), "")


class TestRssFilter(unittest.TestCase):
    def test_strict_feed_requires_exclusive_keyword(self):
        feed = {"id": "17173"}
        # 只有泛词“合成/消除”，严格源应丢弃
        self.assertFalse(rss.is_relevant("全球使命3 限时免费合成", "", feed, CONFIG, CONFIG["games"]))
        self.assertFalse(rss.is_relevant("某休闲消除游戏分析", "", feed, CONFIG, CONFIG["games"]))
        # 命中游戏名 / 二合专有词 / 厂商
        self.assertTrue(rss.is_relevant("Gossip Harbor 新活动", "", feed, CONFIG, CONFIG["games"]))
        self.assertTrue(rss.is_relevant("二合赛道新作", "", feed, CONFIG, CONFIG["games"]))
        self.assertTrue(rss.is_relevant("柠檬微趣发布新游", "", feed, CONFIG, CONFIG["games"]))

    def test_general_feed_accepts_any_keyword(self):
        feed = {"id": "appgrowing"}
        self.assertTrue(rss.is_relevant("休闲消除赛道月报", "", feed, CONFIG, CONFIG["games"]))
        self.assertFalse(rss.is_relevant("Saudi fund buys a studio", "", feed, CONFIG, CONFIG["games"]))

    def test_keyword_boundary(self):
        # emergency 不应命中 merge；合并 / 合成 命中
        self.assertFalse(rss._keyword_hit("emergency patch", "merge"))
        self.assertTrue(rss._keyword_hit("merge patch", "merge"))
        self.assertTrue(rss._keyword_hit("公司合并公告", "合并"))

    def test_make_draft_expands_and_cleans(self):
        item = rss.parse_feed(RSS_XML)[0]
        draft = rss.make_draft({"id": "appgrowing", "lang": "zh"}, item, TODAY, "2026-11-03T07:00:00+08:00")
        self.assertIsNotNone(draft)
        self.assertTrue(draft["id"].startswith("draft-20261103-appgrowing-"))
        self.assertEqual(draft["publishedAt"], "2026-10-16")
        self.assertEqual(draft["url"], "https://example.com/a")
        self.assertNotIn("#top", draft["url"])
        self.assertIn("赛季通行证", draft["excerpt"])
        self.assertNotIn("<b>", draft["excerpt"])
        self.assertEqual(draft["aiStatus"], "none")
        self.assertIsNone(draft["relevance"])

    def test_17173_missing_date_uses_url(self):
        item = {
            "title": "Gossip Harbor 更新",
            "link": "http://news.17173.com/content/11032026/120358043.shtml",
            "date": "",
            "description": "",
        }
        draft = rss.make_draft({"id": "17173"}, item, TODAY)
        self.assertEqual(draft["publishedAt"], "2026-11-03")

    def test_make_draft_rejects_bad_item(self):
        self.assertIsNone(rss.make_draft({"id": "x"}, {"title": "", "link": "https://a.com"}, TODAY))
        self.assertIsNone(rss.make_draft({"id": "x"}, {"title": "t", "link": "javascript:void(0)"}, TODAY))


class FakeClient:
    """最小 HTTP mock：按 URL 返回文本或抛错。"""

    def __init__(self, responses):
        self.responses = responses

    def get_text(self, url, headers=None):
        value = self.responses[url]
        if isinstance(value, Exception):
            raise value
        return value


class TestRssFetch(unittest.TestCase):
    def test_fetch_drafts_isolates_failures(self):
        config = {
            "keywords": CONFIG["keywords"],
            "games": CONFIG["games"],
            "feeds": [
                {"id": "appgrowing", "url": "https://feed/a", "enabled": True, "lang": "zh"},
                {"id": "17173", "url": "https://feed/b", "enabled": True, "lang": "zh"},
                {"id": "baijing", "url": "https://feed/c", "enabled": False, "lang": "zh"},
            ],
        }
        client = FakeClient({"https://feed/a": RSS_XML, "https://feed/b": RuntimeError("boom")})
        drafts, statuses = rss.fetch_drafts(client, config, CONFIG["games"], today_value=TODAY)
        self.assertEqual(len(statuses), 2)  # disabled feed 跳过
        self.assertTrue(statuses["rss_appgrowing"]["ok"])
        self.assertFalse(statuses["rss_17173"]["ok"])
        self.assertIn("boom", statuses["rss_17173"]["error"])
        # appgrowing 非严格源：4 条里命中含关键词的（含泛词/emergency 不应命中 merge）
        titles = [draft["title"] for draft in drafts]
        self.assertTrue(any("Gossip Harbor" in title for title in titles))

    def test_fetch_feed_counts_and_filters(self):
        client = FakeClient({"https://feed/a": RSS_XML})
        drafts, status = rss.fetch_feed(
            client, {"id": "appgrowing", "url": "https://feed/a"}, CONFIG, CONFIG["games"],
            today_value=TODAY,
        )
        self.assertTrue(status["ok"])
        self.assertEqual(status["items"], len(drafts))
        self.assertGreater(len(drafts), 0)


class TestRssMerge(unittest.TestCase):
    def _draft(self, url, day, title="t"):
        return {
            "id": f"draft-{day}-x-{url[-1]}",
            "title": title,
            "excerpt": "",
            "url": url,
            "sourceId": "x",
            "publishedAt": day,
            "lang": "zh",
            "fetchedAt": "2026-11-03T07:00:00+08:00",
            "aiStatus": "none",
            "relevance": None,
        }

    def test_url_dedupe_against_existing(self):
        existing = {"drafts": [self._draft("https://example.com/a?id=1", "2026-10-20")], "updatedAt": ""}
        new = [
            self._draft("https://example.com/a?id=1&utm_source=x", "2026-10-20", "dup"),
            self._draft("https://example.com/b", "2026-10-21", "new"),
        ]
        merged = rss.merge_drafts(existing, new, TODAY)
        self.assertEqual(len(merged["drafts"]), 2)
        titles = {draft["title"] for draft in merged["drafts"]}
        self.assertIn("new", titles)
        self.assertNotIn("dup", titles)

    def test_max_new_per_run(self):
        new = [self._draft(f"https://example.com/{index}", "2026-11-0%d" % (index + 1)) for index in range(5)]
        merged = rss.merge_drafts({}, new, TODAY, max_new_per_run=2)
        self.assertEqual(len(merged["drafts"]), 2)

    def test_retention_and_max(self):
        old = (TODAY - timedelta(days=200)).isoformat()
        existing = {"drafts": [self._draft("https://example.com/old", old)], "updatedAt": ""}
        recent = [self._draft(f"https://example.com/{index}", "2026-11-01") for index in range(5)]
        merged = rss.merge_drafts(existing, recent, TODAY, max_drafts=3)
        self.assertLessEqual(len(merged["drafts"]), 3)
        urls = [draft["url"] for draft in merged["drafts"]]
        self.assertNotIn("https://example.com/old", urls)


# -- AI -------------------------------------------------------------------
def make_draft(index: int, title: str = "") -> dict:
    return {
        "id": f"draft-20261103-src-{index}",
        "title": title or f"线索 {index}",
        "excerpt": f"摘要 {index}",
        "url": f"https://example.com/item/{index}",
        "sourceId": "appgrowing",
        "publishedAt": "2026-10-16",
        "lang": "zh",
        "fetchedAt": "2026-11-03T07:00:00+08:00",
        "aiStatus": "none",
        "relevance": None,
    }


def results_for_prompt(user_prompt: str, custom=None) -> dict:
    """按 user prompt 里的 index 生成模型结果，供 transport mock 使用。"""
    payload = json.loads(user_prompt)
    items = []
    for entry in payload["items"]:
        index = entry["index"]
        if custom and index in custom:
            items.append(custom[index])
            continue
        items.append({
            "index": index,
            "relevance": 0.9,
            "summary": "这是一条足够长的中文摘要，用于测试 AI 提炼输出的字段完整性。" * 2,
            "takeaway": "关注活动节奏与付费结构，结合本周榜单复盘。",
            "dimensions": ["activity", "market"],
            "gameIds": ["gossip-harbor", "unknown-game"],
            "importance": 2,
            "tags": ["活动", "榜单"],
            "confidence": "high",
        })
    return {"items": items}


class TestAiKey(unittest.TestCase):
    def test_env_key_priority(self):
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "env-key-123"}):
            self.assertEqual(ai_mod.resolve_api_key(), "env-key-123")

    def test_secrets_file_and_missing(self):
        with mock.patch.dict(os.environ, {}, clear=True), workspace_tmpdir() as temp_dir:
            path = Path(temp_dir) / "secrets.json"
            path.write_text(json.dumps({"deepseek_api_key": "file-key-456"}), encoding="utf-8")
            self.assertEqual(ai_mod.resolve_api_key(path), "file-key-456")
            missing = Path(temp_dir) / "nope.json"
            self.assertEqual(ai_mod.resolve_api_key(missing), "")

    def test_cache_key_stable(self):
        first = ai_mod.cache_key("deepseek-chat", "sys", "user")
        second = ai_mod.cache_key("deepseek-chat", "sys", "user")
        self.assertEqual(first, second)
        self.assertNotEqual(first, ai_mod.cache_key("deepseek-chat", "sys", "other"))


class TestAiClient(unittest.TestCase):
    def test_transport_and_fenced_json(self):
        def transport(system, user):
            return "```json\n" + json.dumps({"items": []}) + "\n```"

        client = ai_mod.AiClient(transport=transport)
        self.assertTrue(client.available)
        self.assertEqual(client.chat("s", "u"), {"items": []})

    def test_no_key_not_available(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            client = ai_mod.AiClient(api_key="")
        self.assertFalse(client.available)
        self.assertNotIn("key", repr(client).lower().replace("available", ""))
        with self.assertRaises(ai_mod.AiError):
            client.chat("s", "u")

    def test_bad_json_raises_ai_error(self):
        client = ai_mod.AiClient(transport=lambda system, user: "not json at all")
        with self.assertRaises(ai_mod.AiError):
            client.chat("s", "u")


class TestAiEnrich(unittest.TestCase):
    def test_no_key_degrades_all_drafts(self):
        drafts = [make_draft(0), make_draft(1)]
        with mock.patch.dict(os.environ, {}, clear=True):
            client = ai_mod.AiClient(api_key="")
        updated, items, stats, cache = ai_mod.enrich_drafts(
            client, drafts, CONFIG, {}, CONFIG["games"], "2026-11-03T07:00:00+08:00"
        )
        self.assertFalse(stats["available"])
        self.assertEqual(stats["skipped"], 2)
        self.assertEqual(items, [])
        self.assertTrue(all(draft["aiStatus"] == "none" for draft in updated["drafts"]))

    def test_enrich_high_confidence_writes_item(self):
        client = ai_mod.AiClient(transport=lambda system, user: results_for_prompt(user))
        drafts = [make_draft(0, "Gossip Harbor 活动更新"), make_draft(1, "Merge Mansion 联动")]
        updated, items, stats, cache = ai_mod.enrich_drafts(
            client, drafts, CONFIG, {}, CONFIG["games"], "2026-11-03T07:00:00+08:00"
        )
        self.assertEqual(stats["calls"], 1)
        self.assertEqual(stats["enriched"], 2)
        self.assertEqual(len(items), 2)
        item = items[0]
        self.assertTrue(item["id"].startswith("ai-"))
        self.assertEqual(item["summaryBy"], "ai")
        self.assertEqual(item["sourceId"], "appgrowing")
        self.assertEqual(item["url"], "https://example.com/item/0")
        self.assertEqual(item["gameIds"], ["gossip-harbor"])  # 未知 gameId 被过滤
        self.assertIn("activity", item["dimensions"])
        self.assertEqual(item["importance"], 2)
        self.assertEqual(item["confidence"], "high")
        self.assertTrue(updated["drafts"][0]["aiStatus"] == "enriched")
        self.assertGreater(updated["drafts"][0]["relevance"], 0.8)
        self.assertTrue(cache)

    def test_low_relevance_rejected_and_incomplete_stays_none(self):
        custom = {
            0: {"index": 0, "relevance": 0.2, "confidence": "low"},
            1: {
                "index": 1,
                "relevance": 0.9,
                "summary": "太短",
                "takeaway": "",
                "dimensions": [],
                "confidence": "medium",
            },
        }
        client = ai_mod.AiClient(transport=lambda system, user: results_for_prompt(user, custom))
        drafts = [make_draft(0), make_draft(1)]
        updated, items, stats, cache = ai_mod.enrich_drafts(
            client, drafts, CONFIG, {}, CONFIG["games"], "2026-11-03T07:00:00+08:00"
        )
        self.assertEqual(items, [])
        self.assertEqual(updated["drafts"][0]["aiStatus"], "rejected")
        self.assertEqual(updated["drafts"][1]["aiStatus"], "none")
        self.assertEqual(stats["rejected"], 1)
        self.assertEqual(stats["skipped"], 1)

    def test_cache_hit_avoids_second_call(self):
        calls = {"count": 0}

        def transport(system, user):
            calls["count"] += 1
            return results_for_prompt(user)

        client = ai_mod.AiClient(transport=transport)
        drafts = [make_draft(0)]
        _, _, stats1, cache = ai_mod.enrich_drafts(
            client, drafts, CONFIG, {}, CONFIG["games"], "2026-11-03T07:00:00+08:00"
        )
        self.assertEqual(calls["count"], 1)
        self.assertEqual(stats1["calls"], 1)
        # 用同一份缓存、新的 pending drafts 再跑：应命中缓存不再调用
        fresh = [make_draft(0)]
        _, _, stats2, _ = ai_mod.enrich_drafts(
            client, fresh, CONFIG, cache, CONFIG["games"], "2026-11-03T07:00:00+08:00"
        )
        self.assertEqual(calls["count"], 1)
        self.assertEqual(stats2["cached"], 1)
        self.assertEqual(stats2["calls"], 0)

    def test_batching_by_max_items_per_call(self):
        calls = {"count": 0}

        def transport(system, user):
            calls["count"] += 1
            return results_for_prompt(user)

        client = ai_mod.AiClient(transport=transport)
        drafts = [make_draft(index) for index in range(9)]
        cfg = {"ai": dict(CONFIG["ai"], maxItemsPerCall=4)}
        _, items, stats, _ = ai_mod.enrich_drafts(
            client, drafts, cfg, {}, CONFIG["games"], "2026-11-03T07:00:00+08:00"
        )
        self.assertEqual(calls["count"], 3)
        self.assertEqual(stats["calls"], 3)
        self.assertEqual(len(items), 9)

    def test_call_failure_degrades_without_items(self):
        def transport(system, user):
            raise ai_mod.AiError("HTTP 500")

        client = ai_mod.AiClient(transport=transport)
        updated, items, stats, _ = ai_mod.enrich_drafts(
            client, [make_draft(0)], CONFIG, {}, CONFIG["games"], "2026-11-03T07:00:00+08:00"
        )
        self.assertEqual(items, [])
        self.assertEqual(stats["failed"], 1)
        self.assertEqual(updated["drafts"][0]["aiStatus"], "none")
        status = ai_mod.make_status_entry(stats, key_present=True)
        self.assertFalse(status["ok"])
        self.assertIn("失败", status["error"])
        # 状态里绝不能出现 key
        self.assertNotIn("sk", status["error"].lower())

    def test_max_calls_per_run_limits(self):
        calls = {"count": 0}

        def transport(system, user):
            calls["count"] += 1
            return results_for_prompt(user)

        client = ai_mod.AiClient(transport=transport)
        cfg = {"ai": dict(CONFIG["ai"], maxItemsPerCall=1, maxCallsPerRun=1)}
        drafts = [make_draft(index) for index in range(3)]
        updated, items, stats, _ = ai_mod.enrich_drafts(
            client, drafts, cfg, {}, CONFIG["games"], "2026-11-03T07:00:00+08:00"
        )
        self.assertEqual(calls["count"], 1)
        self.assertEqual(len(items), 1)
        self.assertGreaterEqual(stats["skipped"], 2)


class TestAiItems(unittest.TestCase):
    def test_build_item_filters_and_defaults(self):
        draft = make_draft(0, "Merge Mansion 新版本")
        result = {
            "relevance": 0.95,
            "summary": "这是一条足够长的中文摘要，用于测试字段过滤与默认值处理逻辑。" * 2,
            "takeaway": "下周复盘活动节奏。",
            "dimensions": ["activity", "bogus"],
            "gameIds": ["merge-mansion", "not-exist"],
            "importance": 99,
            "tags": ["版本"],
            "confidence": "weird",
        }
        item = ai_mod.build_item(draft, result, CONFIG["games"], "2026-11-03T07:00:00+08:00")
        self.assertIsNotNone(item)
        self.assertEqual(item["dimensions"], ["activity"])
        self.assertEqual(item["gameIds"], ["merge-mansion"])
        self.assertEqual(item["importance"], 2)
        self.assertEqual(item["confidence"], "medium")
        self.assertEqual(item["summaryBy"], "ai")
        self.assertEqual(item["createdAt"], "2026-11-03")

    def test_build_item_rejects_low_relevance_and_empty(self):
        draft = make_draft(0)
        self.assertIsNone(ai_mod.build_item(draft, {"relevance": 0.1, "summary": "x" * 30,
                                                    "takeaway": "abcde", "dimensions": ["market"]}))
        self.assertIsNone(ai_mod.build_item(draft, {"relevance": 0.9}))

    def test_merge_items_auto_dedupe_and_cap(self):
        existing = {"items": [{"id": "ai-a", "publishedAt": "2026-11-01"}], "updatedAt": ""}
        new = [
            {"id": "ai-a", "publishedAt": "2026-11-01"},
            {"id": "ai-b", "publishedAt": "2026-11-02"},
        ]
        merged = ai_mod.merge_items_auto(existing, new, TODAY, max_items=2)
        ids = [item["id"] for item in merged["items"]]
        self.assertEqual(sorted(ids), ["ai-a", "ai-b"])

    def test_context_window_never_contains_key(self):
        captured = {}

        def transport(system, user):
            captured["system"] = system
            captured["user"] = user
            return results_for_prompt(user)

        client = ai_mod.AiClient(api_key="super-secret-key", transport=transport)
        _, _, stats, _ = ai_mod.enrich_drafts(
            client, [make_draft(0)], CONFIG, {}, CONFIG["games"], "2026-11-03T07:00:00+08:00"
        )
        self.assertNotIn("super-secret-key", captured["system"] + captured["user"])
        self.assertNotIn("super-secret-key", json.dumps(stats))


if __name__ == "__main__":
    unittest.main()
