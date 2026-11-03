"""采集核心测试（stdlib unittest，不联网）。

覆盖：榜单解析、charts 合并/去重/裁剪、版本解析与去重/上限、告警规则
（首次基线不误报、top5、rank-jump、version、suspect-hit、同日去重）、
store 原子写与状态合并。

运行：python tools/tests/run_tests.py
"""
from __future__ import annotations

import contextlib
import json
import shutil
import unittest
import uuid
from datetime import date, timedelta
from pathlib import Path

from collect_lib import alerts, appstore, charts, store

FIXTURES = Path(__file__).resolve().parent / "fixtures"
TODAY = date(2026, 11, 3)

GAMES = [
    {
        "id": "gossip-harbor",
        "name": "Gossip Harbor",
        "nameZh": "浪漫餐厅",
        "stores": {"cn": "6472696051", "us": "1623318294"},
    },
    {
        "id": "merge-cooking",
        "name": "Merge Cooking",
        "nameZh": "Merge Cooking",
        "stores": {"us": "1643509748"},
    },
    {
        "id": "merge-mansion",
        "name": "Merge Mansion",
        "nameZh": "Merge Mansion",
        "stores": {"us": "1484442152"},
    },
]


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@contextlib.contextmanager
def workspace_tmpdir():
    """在 workspace 内建临时目录。

    注意：不用 tempfile.TemporaryDirectory —— 它按 0700 创建目录，
    在本机 DSH 沙箱下会导致后续写入/清理被拒绝；这里用 0755。
    """
    root = Path(__file__).resolve().parent / "_tmp"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"case_{uuid.uuid4().hex[:10]}"
    path.mkdir(mode=0o755)
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


def make_snapshot(country: str, kind_id: str, entries, day: str = "2026-11-02",
                  label: str = "Puzzle 畅销") -> dict:
    return {
        "date": day,
        "country": country,
        "kindId": kind_id,
        "kind": "topgrossingapplications",
        "genre": 7012,
        "label": label,
        "entries": [
            {"rank": rank, "appId": str(app_id), "name": name, "publisher": publisher}
            for rank, (app_id, name, publisher) in enumerate(entries, start=1)
        ],
    }


def make_version(game_id: str, store_key: str, version: str, released_at: str,
                 notes: str = "", record_id: str = "") -> dict:
    record_id = record_id or f"version-{game_id}-{store_key}-{version}-{released_at}"
    return {
        "id": record_id,
        "gameId": game_id,
        "store": store_key,
        "version": version,
        "releasedAt": released_at,
        "notes": notes,
        "notesUrl": f"https://apps.apple.com/{store_key}/app/id1",
        "ratingCount": None,
        "averageRating": None,
        "highlights": [],
        "fetchedAt": "2026-11-01T00:00:00+08:00",
    }


class TestAppstoreUrls(unittest.TestCase):
    def test_lookup_url_batches_ids(self):
        url = appstore.lookup_url(["1623318294", "1484442152"], "us")
        self.assertIn("id=1623318294,1484442152", url)
        self.assertIn("country=us", url)
        self.assertIn("lang=en_us", url)

    def test_lookup_url_cn_lang(self):
        self.assertIn("lang=zh_cn", appstore.lookup_url(["6472696051"], "cn"))

    def test_chart_url_with_and_without_genre(self):
        self.assertEqual(
            charts.chart_url("us", "topgrossingapplications", 7012),
            "https://itunes.apple.com/us/rss/topgrossingapplications/limit=50/genre=7012/json",
        )
        self.assertEqual(
            charts.chart_url("jp", "topfreeapplications", None),
            "https://itunes.apple.com/jp/rss/topfreeapplications/limit=50/json",
        )


class TestChartParse(unittest.TestCase):
    def test_parse_fixture_ranks_in_order(self):
        entries = charts.parse_chart_feed(load_fixture("chart_us_puzzle.json"))
        self.assertEqual(len(entries), 5)
        self.assertEqual(entries[0]["rank"], 1)
        self.assertEqual(entries[0]["name"], "Royal Match")
        self.assertEqual(entries[0]["appId"], "1482155847")
        self.assertEqual(entries[0]["publisher"], "Dream Games, Ltd.")
        self.assertEqual(entries[1]["appId"], "1623318294")
        self.assertEqual(entries[3]["appId"], "1484442152")
        # 缺 attributes 时从 label URL 兜底解析
        self.assertEqual(entries[4]["appId"], "999999999")

    def test_parse_empty_feed(self):
        self.assertEqual(charts.parse_chart_feed({"feed": {}}), [])
        self.assertEqual(charts.parse_chart_feed(None), [])

    def test_single_entry_dict_is_supported(self):
        payload = {
            "feed": {
                "entry": {
                    "im:name": {"label": "Solo"},
                    "im:artist": {"label": "Studio"},
                    "id": {"attributes": {"im:id": "123456789"}},
                }
            }
        }
        entries = charts.parse_chart_feed(payload)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["rank"], 1)


class TestMergeCharts(unittest.TestCase):
    def test_latest_replaces_same_country_kind(self):
        day1 = make_snapshot("us", "puzzle-grossing",
                             [("1", "A", "X"), ("2", "B", "Y")], "2026-11-02")
        merged = charts.merge_charts({}, [day1], GAMES, TODAY)
        self.assertEqual(len(merged["latest"]), 1)

        day2 = make_snapshot("us", "puzzle-grossing",
                             [("3", "C", "Z"), ("1", "A", "X")], "2026-11-03")
        merged = charts.merge_charts(merged, [day2], GAMES, TODAY)
        self.assertEqual(len(merged["latest"]), 1)
        self.assertEqual(merged["latest"][0]["date"], "2026-11-03")
        self.assertEqual(merged["latest"][0]["entries"][0]["appId"], "3")

    def test_top5_same_day_overwrites_not_appends(self):
        snap = make_snapshot("us", "puzzle-grossing",
                             [("1623318294", "Gossip Harbor", "Microfun")], "2026-11-03")
        merged = charts.merge_charts({}, [snap], GAMES, TODAY)
        self.assertEqual(len(merged["top5"]), 1)
        merged = charts.merge_charts(merged, [snap], GAMES, TODAY)
        self.assertEqual(len(merged["top5"]), 1)
        self.assertEqual(merged["top5"][0]["date"], "2026-11-03")
        self.assertEqual(merged["top5"][0]["entries"][0]["appId"], "1623318294")

    def test_top5_keeps_previous_days(self):
        snap1 = make_snapshot("us", "puzzle-grossing", [("1", "A", "X")], "2026-11-02")
        snap2 = make_snapshot("us", "puzzle-grossing", [("1", "A", "X")], "2026-11-03")
        merged = charts.merge_charts({}, [snap1], GAMES, TODAY - timedelta(days=1))
        merged = charts.merge_charts(merged, [snap2], GAMES, TODAY)
        self.assertEqual(len(merged["top5"]), 2)

    def test_rank_history_only_config_games_and_dedupe_by_date(self):
        snap = make_snapshot("us", "puzzle-grossing", [
            ("1623318294", "Gossip Harbor", "Microfun"),
            ("999999999", "Unknown", "Nobody"),
        ], "2026-11-02")
        merged = charts.merge_charts({}, [snap], GAMES, TODAY)
        self.assertIn("gossip-harbor", merged["rankHistory"])
        self.assertNotIn("999999999", merged["rankHistory"])
        points = merged["rankHistory"]["gossip-harbor"]["us"]["puzzle-grossing"]
        self.assertEqual(points, [["2026-11-02", 1]])

        snap_day3 = make_snapshot("us", "puzzle-grossing", [
            ("1623318294", "Gossip Harbor", "Microfun"),
        ], "2026-11-03")
        merged = charts.merge_charts(merged, [snap_day3], GAMES, TODAY)
        points = merged["rankHistory"]["gossip-harbor"]["us"]["puzzle-grossing"]
        self.assertEqual(len(points), 2)

        # 同一天重跑：覆盖同日期而非追加
        snap_day3_again = make_snapshot("us", "puzzle-grossing", [
            ("1623318294", "Gossip Harbor", "Microfun"),
            ("1643509748", "Merge Cooking", "Happibits"),
        ], "2026-11-03")
        merged = charts.merge_charts(merged, [snap_day3_again], GAMES, TODAY)
        points = merged["rankHistory"]["gossip-harbor"]["us"]["puzzle-grossing"]
        self.assertEqual(len(points), 2)

    def test_rank_history_trims_old_dates(self):
        old_day = (TODAY - timedelta(days=100)).isoformat()
        existing = {
            "latest": [],
            "top5": [],
            "rankHistory": {
                "gossip-harbor": {"us": {"puzzle-grossing": [[old_day, 12], ["2026-11-02", 9]]}}
            },
            "updatedAt": "",
        }
        snap = make_snapshot("us", "puzzle-grossing", [
            ("1623318294", "Gossip Harbor", "Microfun"),
        ], "2026-11-03")
        merged = charts.merge_charts(existing, [snap], GAMES, TODAY)
        points = merged["rankHistory"]["gossip-harbor"]["us"]["puzzle-grossing"]
        dates = [point[0] for point in points]
        self.assertNotIn(old_day, dates)
        self.assertIn("2026-11-03", dates)
        self.assertIn("2026-11-02", dates)

    def test_failed_snapshot_keeps_old_latest(self):
        old = make_snapshot("us", "puzzle-grossing", [("1", "A", "X")], "2026-11-01")
        existing = {"latest": [old], "top5": [], "rankHistory": {}, "updatedAt": ""}
        merged = charts.merge_charts(existing, [], GAMES, TODAY)
        self.assertEqual(len(merged["latest"]), 1)
        self.assertEqual(merged["latest"][0]["date"], "2026-11-01")


class TestVersions(unittest.TestCase):
    def test_records_from_lookup_fixture(self):
        payload = load_fixture("lookup_us.json")
        mapping = {"1623318294": "gossip-harbor", "1484442152": "merge-mansion"}
        records = appstore.records_from_lookup(payload, "us", mapping, "2026-11-03T07:00:00+08:00")
        self.assertEqual(len(records), 2)
        first = records[0]
        self.assertEqual(first["gameId"], "gossip-harbor")
        self.assertEqual(first["store"], "us")
        self.assertEqual(first["version"], "4.11.0")
        self.assertEqual(first["releasedAt"], "2026-10-27")
        self.assertEqual(first["ratingCount"], 12345)
        self.assertAlmostEqual(first["averageRating"], 4.72)
        self.assertTrue(first["notesUrl"].startswith("https://apps.apple.com/"))
        self.assertTrue(first["id"].startswith("version-gossip-harbor-us-4.11.0-2026-10-27"))
        self.assertNotIn("_trackName", first)

    def test_notes_truncated_to_2000(self):
        result = {
            "trackId": 1,
            "version": "1.0.0",
            "currentVersionReleaseDate": "2026-10-01T00:00:00Z",
            "releaseNotes": "活" * 3000,
        }
        record = appstore.make_version_record("demo", "us", result)
        self.assertLessEqual(len(record["notes"]), 2000)
        self.assertTrue(record["notes"].endswith("…"))

    def test_merge_dedupes_same_version(self):
        record = make_version("gossip-harbor", "us", "4.11.0", "2026-10-27")
        merged = appstore.merge_versions([], [record, dict(record)])
        self.assertEqual(len(merged), 1)
        merged_again = appstore.merge_versions(merged, [record])
        self.assertEqual(len(merged_again), 1)

    def test_same_version_new_date_updates(self):
        old = make_version("gossip-harbor", "us", "4.11.0", "2026-10-20",
                           record_id="version-gossip-harbor-us-4.11.0-2026-10-20")
        new = make_version("gossip-harbor", "us", "4.11.0", "2026-10-27",
                           notes="新增限时活动",
                           record_id="version-gossip-harbor-us-4.11.0-2026-10-27")
        merged = appstore.merge_versions([old], [new])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["releasedAt"], "2026-10-27")
        self.assertEqual(merged[0]["notes"], "新增限时活动")
        self.assertTrue(merged[0]["id"].endswith("2026-10-27"))

    def test_keeps_only_latest_20_per_game_store(self):
        records = []
        base = date(2026, 9, 1)
        for index in range(25):
            released = (base + timedelta(days=index)).isoformat()
            records.append(make_version("gossip-harbor", "us", f"1.{index}.0", released))
        merged = appstore.merge_versions([], records)
        self.assertEqual(len(merged), 20)
        versions = [record["version"] for record in merged]
        self.assertEqual(versions[0], "1.24.0")
        self.assertNotIn("1.4.0", versions)
        self.assertIn("1.5.0", versions)

    def test_sorted_desc_by_release_date(self):
        records = [
            make_version("gossip-harbor", "us", "4.10.0", "2026-09-01"),
            make_version("gossip-harbor", "cn", "4.11.0", "2026-10-27"),
        ]
        merged = appstore.merge_versions([], records)
        self.assertEqual([record["releasedAt"] for record in merged],
                         ["2026-10-27", "2026-09-01"])


class TestAlerts(unittest.TestCase):
    def _state(self, day: str, ranks: dict) -> dict:
        return {"date": day, "ranks": ranks, "updatedAt": ""}

    def test_first_run_baseline_no_alerts(self):
        snap = make_snapshot("us", "puzzle-grossing", [
            ("1623318294", "Gossip Harbor", "Microfun"),
        ], "2026-11-03")
        self.assertEqual(alerts.detect_chart_alerts({}, [snap], GAMES, "2026-11-03"), [])
        self.assertEqual(alerts.detect_chart_alerts(None, [snap], GAMES, "2026-11-03"), [])

    def test_top5_entry_triggers_high_confidence_alert(self):
        prev = self._state("2026-11-02", {"us": {"puzzle-grossing": {"1623318294": 9}}})
        snap = make_snapshot("us", "puzzle-grossing", [
            ("111", "Other", "X"),
            ("222", "Other2", "Y"),
            ("1623318294", "Gossip Harbor", "Microfun"),
        ], "2026-11-03")
        result = alerts.detect_chart_alerts(prev, [snap], GAMES, "2026-11-03")
        top5 = [alert for alert in result if alert["type"] == "top5"]
        self.assertEqual(len(top5), 1)
        alert = top5[0]
        self.assertEqual(alert["gameId"], "gossip-harbor")
        self.assertEqual(alert["rank"], 3)
        self.assertEqual(alert["prevRank"], 9)
        self.assertEqual(alert["confidence"], "high")
        self.assertEqual(alert["sourceUrl"], "https://apps.apple.com/us/app/id1623318294")
        self.assertIn("第 3", alert["summary"])

    def test_top5_stays_does_not_repeat(self):
        prev = self._state("2026-11-02", {"us": {"puzzle-grossing": {"1623318294": 3}}})
        snap = make_snapshot("us", "puzzle-grossing", [
            ("111", "Other", "X"),
            ("222", "Other2", "Y"),
            ("1623318294", "Gossip Harbor", "Microfun"),
        ], "2026-11-03")
        self.assertEqual(alerts.detect_chart_alerts(prev, [snap], GAMES, "2026-11-03"), [])

    def test_top5_reentry_alerts_again(self):
        prev = self._state("2026-11-02", {"us": {"puzzle-grossing": {"1623318294": 7}}})
        snap = make_snapshot("us", "puzzle-grossing", [
            ("111", "Other", "X"),
            ("222", "Other2", "Y"),
            ("1623318294", "Gossip Harbor", "Microfun"),
        ], "2026-11-03")
        result = alerts.detect_chart_alerts(prev, [snap], GAMES, "2026-11-03")
        self.assertEqual(len([alert for alert in result if alert["type"] == "top5"]), 1)

    def test_same_day_rerun_skips_comparison(self):
        prev = self._state("2026-11-03", {"us": {"puzzle-grossing": {"1623318294": 9}}})
        snap = make_snapshot("us", "puzzle-grossing", [
            ("111", "Other", "X"),
            ("222", "Other2", "Y"),
            ("1623318294", "Gossip Harbor", "Microfun"),
        ], "2026-11-03")
        self.assertEqual(alerts.detect_chart_alerts(prev, [snap], GAMES, "2026-11-03"), [])

    def test_rank_jump_threshold(self):
        prev = self._state("2026-11-02", {"us": {"overall-grossing": {"1623318294": 30}}})
        snap = make_snapshot("us", "overall-grossing", [
            ("a", "A", "X"), ("b", "B", "X"), ("c", "C", "X"), ("d", "D", "X"),
            ("e", "E", "X"), ("f", "F", "X"), ("g", "G", "X"), ("h", "H", "X"),
            ("i", "I", "X"), ("1623318294", "Gossip Harbor", "Microfun"),
        ], "2026-11-03", label="综合畅销")
        result = alerts.detect_chart_alerts(prev, [snap], GAMES, "2026-11-03")
        jumps = [alert for alert in result if alert["type"] == "rank-jump"]
        self.assertEqual(len(jumps), 1)
        self.assertEqual(jumps[0]["prevRank"], 30)
        self.assertEqual(jumps[0]["rank"], 10)

        prev_small = self._state("2026-11-02", {"us": {"overall-grossing": {"1623318294": 20}}})
        result_small = alerts.detect_chart_alerts(prev_small, [snap], GAMES, "2026-11-03")
        self.assertEqual([alert for alert in result_small if alert["type"] == "rank-jump"], [])

    def test_unknown_merge_lookalike_is_suspect_hit(self):
        prev = self._state("2026-11-02", {"us": {"puzzle-grossing": {"888888888": 15}}})
        snap = make_snapshot("us", "puzzle-grossing", [
            ("111", "Other", "X"),
            ("888888888", "Merge Dream Island", "Some Studio"),
        ], "2026-11-03")
        result = alerts.detect_chart_alerts(prev, [snap], GAMES, "2026-11-03")
        suspects = [alert for alert in result if alert["type"] == "suspect-hit"]
        self.assertEqual(len(suspects), 1)
        self.assertEqual(suspects[0]["appId"], "888888888")
        self.assertNotIn("gameId", suspects[0])
        self.assertEqual(suspects[0]["confidence"], "low")

    def test_unknown_generic_puzzle_not_reported(self):
        prev = self._state("2026-11-02", {"us": {"puzzle-grossing": {"888888888": 15}}})
        snap = make_snapshot("us", "puzzle-grossing", [
            ("888888888", "Candy Blast", "Generic Studio"),
        ], "2026-11-03")
        result = alerts.detect_chart_alerts(prev, [snap], GAMES, "2026-11-03")
        self.assertEqual(result, [])

    def test_version_alert_with_keywords(self):
        previous = [make_version("gossip-harbor", "us", "4.10.0", "2026-10-01")]
        current = previous + [
            make_version("gossip-harbor", "us", "4.11.0", "2026-10-27",
                         notes="新增限时活动「秋日庆典」与赛季通行证")
        ]
        result = alerts.detect_version_alerts(previous, current, GAMES, "2026-11-03")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "version")
        self.assertEqual(result[0]["gameId"], "gossip-harbor")
        self.assertIn("4.11.0", result[0]["summary"])
        self.assertTrue(result[0]["id"].startswith("alert-20261103-us-"))

    def test_version_without_keywords_ignored(self):
        previous = [make_version("gossip-harbor", "us", "4.10.0", "2026-10-01")]
        current = previous + [
            make_version("gossip-harbor", "us", "4.11.0", "2026-10-27", notes="修复若干问题")
        ]
        self.assertEqual(alerts.detect_version_alerts(previous, current, GAMES, "2026-11-03"), [])

    def test_version_first_run_is_baseline(self):
        current = [make_version("gossip-harbor", "us", "4.11.0", "2026-10-27",
                                notes="新增限时活动")]
        self.assertEqual(alerts.detect_version_alerts([], current, GAMES, "2026-11-03"), [])

    def test_same_version_new_date_not_counted_as_new(self):
        previous = [make_version("gossip-harbor", "us", "4.11.0", "2026-10-20",
                                 notes="新增限时活动")]
        current = [make_version("gossip-harbor", "us", "4.11.0", "2026-10-27",
                                notes="新增限时活动")]
        self.assertEqual(alerts.detect_version_alerts(previous, current, GAMES, "2026-11-03"), [])

    def test_alert_state_filters_reported_ids(self):
        alert = {"id": "alert-1", "date": "2026-11-03", "type": "top5"}
        self.assertEqual(len(alerts.filter_new_alerts([alert], {})), 1)
        state = {"reported": {"alert-1": "2026-11-03"}}
        self.assertEqual(alerts.filter_new_alerts([alert], state), [])

    def test_merge_alerts_dedupe_and_retention(self):
        existing = {"alerts": [
            {"id": "alert-old", "date": (TODAY - timedelta(days=200)).isoformat(), "type": "top5"},
            {"id": "alert-keep", "date": "2026-10-30", "type": "top5"},
        ], "updatedAt": ""}
        new = [
            {"id": "alert-keep", "date": "2026-10-30", "type": "top5"},
            {"id": "alert-new", "date": "2026-11-03", "type": "version"},
        ]
        merged = alerts.merge_alerts(existing, new, TODAY)
        ids = [alert["id"] for alert in merged["alerts"]]
        self.assertEqual(sorted(ids), ["alert-keep", "alert-new"])

    def test_merge_alerts_max_limit(self):
        existing = {"alerts": [
            {"id": f"alert-{index}", "date": "2026-11-%02d" % (index + 1), "type": "top5"}
            for index in range(5)
        ], "updatedAt": ""}
        merged = alerts.merge_alerts(existing, [], TODAY, max_alerts=3)
        self.assertEqual(len(merged["alerts"]), 3)


class TestStore(unittest.TestCase):
    def test_atomic_write_leaves_no_tmp(self):
        with workspace_tmpdir() as temp_dir:
            path = Path(temp_dir) / "nested" / "demo.json"
            store.write_json_atomic(path, {"a": "二合", "b": [1, 2]})
            self.assertTrue(path.exists())
            self.assertFalse(path.with_name(path.name + ".tmp").exists())
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["a"], "二合")

    def test_read_json_missing_and_broken(self):
        with workspace_tmpdir() as temp_dir:
            path = Path(temp_dir) / "missing.json"
            self.assertEqual(store.read_json(path, {"fallback": True}), {"fallback": True})
            broken = Path(temp_dir) / "broken.json"
            broken.write_text("{not-json", encoding="utf-8")
            self.assertEqual(store.read_json(broken, {"fallback": True}), {"fallback": True})

    def test_truncate(self):
        self.assertEqual(store.truncate("abc", 10), "abc")
        truncated = store.truncate("x" * 50, 10)
        self.assertLessEqual(len(truncated), 10)
        self.assertTrue(truncated.endswith("…"))

    def test_merge_source_status_keeps_other_sources(self):
        existing = {"sources": {"a": {"ok": True}}, "updatedAt": ""}
        updates = {"b": {"ok": False, "error": "x"}}
        merged = store.merge_source_status(existing, updates, "2026-11-03T07:00:00+08:00")
        self.assertIn("a", merged["sources"])
        self.assertIn("b", merged["sources"])
        self.assertFalse(merged["sources"]["b"]["ok"])

    def test_chart_state_baseline_and_update(self):
        snap = make_snapshot("us", "puzzle-grossing", [
            ("1623318294", "Gossip Harbor", "Microfun"),
        ], "2026-11-03")
        state = charts.chart_state_from_snapshots({}, [snap], TODAY)
        self.assertEqual(state["date"], "2026-11-03")
        self.assertEqual(state["ranks"]["us"]["puzzle-grossing"]["1623318294"], 1)
        # 本轮无快照：保持旧状态
        self.assertEqual(charts.chart_state_from_snapshots(state, [], TODAY), state)


if __name__ == "__main__":
    unittest.main()
