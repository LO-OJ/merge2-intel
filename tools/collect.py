#!/usr/bin/env python3
"""二合情报站采集主入口（零依赖，Python 标准库）。

用法：
    python tools/collect.py                 # 版本 + 榜单 + RSS + 告警 + build（AI 默认关闭）
    python tools/collect.py --dry-run       # 只抓取并打印摘要，不写文件、不 build、不调用 AI
    python tools/collect.py --offline       # 跳过网络，只重建 build（测试用）
    python tools/collect.py --ai            # 启用 DeepSeek 提炼（需 key；失败自动降级）
    python tools/collect.py --no-ai         # 强制关闭 AI（默认即关闭）
    python tools/collect.py --no-build      # 不调用 tools/build.py
    python tools/collect.py --ci            # CI 模式：不打印堆栈，退出码 0/1/2 明确
    python tools/collect.py --only charts   # 调试：只跑某个环节，逗号分隔

退出码：0=至少一个源成功；1=全部失败/配置错误；2=构建校验失败。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from collect_lib import alerts as alerts_mod  # noqa: E402
from collect_lib import ai as ai_mod  # noqa: E402
from collect_lib import appstore, charts as charts_mod, http as http_mod, rss as rss_mod, store  # noqa: E402

FEATURES = ("versions", "charts", "rss", "ai", "alerts")
BUILD_SCRIPT = HERE / "build.py"


# -- 日志 -----------------------------------------------------------------
class Logger:
    """控制台 + tools/logs 文本日志；日志不含密钥。"""

    def __init__(self, log_path: Optional[Path] = None) -> None:
        self.log_path = log_path
        self._handle = None
        if log_path is not None:
            try:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                self._handle = open(log_path, "a", encoding="utf-8", newline="\n")
            except OSError:
                self._handle = None

    def info(self, message: str) -> None:
        print(message)
        if self._handle is not None:
            try:
                self._handle.write(message + "\n")
                self._handle.flush()
            except OSError:
                pass

    def close(self) -> None:
        if self._handle is not None:
            try:
                self._handle.close()
            except OSError:
                pass
            self._handle = None


# -- 参数与配置 -----------------------------------------------------------
def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="二合情报站采集（版本/榜单/告警）")
    parser.add_argument("--config", default=str(HERE / "config.json"), help="配置文件路径")
    parser.add_argument("--dry-run", action="store_true", help="只抓取并打印摘要，不写文件、不 build")
    parser.add_argument("--offline", action="store_true", help="跳过网络，只重建 auto 汇总/build")
    parser.add_argument("--no-ai", action="store_true", help="强制关闭 AI")
    parser.add_argument("--ai", action="store_true", help="启用 DeepSeek 提炼（默认关闭，需 key）")
    parser.add_argument("--no-build", action="store_true", help="不调用 tools/build.py")
    parser.add_argument("--ci", action="store_true", help="CI 模式：不打印异常堆栈，退出码明确")
    parser.add_argument("--only", default="", help="只跑指定环节，逗号分隔：versions,charts,rss,ai,alerts")
    parser.add_argument("--verbose", action="store_true", help="打印异常堆栈（调试用）")
    return parser.parse_args(argv)


def load_config(path: str) -> Tuple[dict, str]:
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    try:
        import json

        with open(config_path, "r", encoding="utf-8") as handle:
            config = json.load(handle)
    except FileNotFoundError:
        return {}, f"配置文件不存在：{config_path}"
    except (OSError, ValueError) as exc:
        return {}, f"配置文件解析失败：{exc}"
    if not isinstance(config, dict):
        return {}, "配置文件顶层必须是对象"
    if not isinstance(config.get("games"), list) or not config.get("games"):
        return {}, "配置缺少 games 数组"
    if not isinstance(config.get("charts", {}), dict):
        return {}, "配置 charts 必须是对象"
    return config, ""


def resolve_features(only: str) -> Tuple[set, str]:
    if not only.strip():
        return set(FEATURES), ""
    wanted = {part.strip() for part in only.split(",") if part.strip()}
    unknown = wanted - set(FEATURES) - {"all"}
    if unknown:
        return set(), f"未知环节：{', '.join(sorted(unknown))}（可选：{', '.join(FEATURES)}, all）"
    if not wanted or "all" in wanted:
        return set(FEATURES), ""
    return wanted, ""


# -- 构建 -----------------------------------------------------------------
def run_build(logger: Logger) -> Tuple[int, str]:
    if not BUILD_SCRIPT.exists():
        return 1, f"构建脚本不存在：{BUILD_SCRIPT}"
    logger.info("  调用 tools/build.py …")
    try:
        completed = subprocess.run(
            [sys.executable, str(BUILD_SCRIPT)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, f"构建进程失败：{type(exc).__name__}: {exc}"
    output = (completed.stdout or "") + (completed.stderr or "")
    return completed.returncode, output.strip()


# -- 主流程 ---------------------------------------------------------------
def _count_new_versions(old_versions: List[dict], merged_versions: List[dict]) -> int:
    old_ids = {str(record.get("id") or "") for record in old_versions}
    return sum(1 for record in merged_versions if str(record.get("id") or "") not in old_ids)


def _chart_limit(config: Mapping[str, Any], key: str, default: int) -> int:
    charts_cfg = config.get("charts") or {}
    try:
        return int(charts_cfg.get(key) or default)
    except (TypeError, ValueError):
        return default


def run(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    config, config_error = load_config(args.config)
    if config_error:
        print(f"配置错误：{config_error}")
        return 1
    wanted, feature_error = resolve_features(args.only)
    if feature_error:
        print(f"参数错误：{feature_error}")
        return 1

    now_iso = store.now_iso()
    today_value = store.today()
    today = today_value.isoformat()
    log_path = None
    if not args.dry_run:
        log_path = store.LOGS_DIR / f"collect-{store.now_cn().strftime('%Y%m%d-%H%M%S')}.log"
    logger = Logger(log_path)
    try:
        logger.info("=" * 60)
        ai_cfg = config.get("ai") or {}
        ai_enabled_flag = (not args.no_ai) and (args.ai or bool(ai_cfg.get("enabled")))
        logger.info(
            f"二合情报站采集 {now_iso}（dry-run={args.dry_run} offline={args.offline} "
            f"ai={'on' if ai_enabled_flag else 'off'}）"
        )
        if log_path is not None:
            logger.info(f"日志：{log_path}")

        games = config.get("games") or []
        collector_cfg = config.get("collector") or {}
        client = http_mod.make_client(collector_cfg, config, logger.info)

        existing_versions = store.load_versions()
        existing_charts = store.load_charts()
        existing_alerts = store.load_alerts()
        existing_status = store.load_source_status()
        previous_chart_state = store.load_state("chart_state", {})
        previous_alert_state = store.load_state("alert_state", {})
        existing_drafts = store.read_json(store.auto_path("drafts.json"), store.EMPTY_DRAFTS)
        if not isinstance(existing_drafts, dict) or not isinstance(existing_drafts.get("drafts"), list):
            existing_drafts = {"drafts": [], "updatedAt": ""}
        existing_items_auto = store.read_json(
            store.auto_path("items-auto.json"), {"items": [], "updatedAt": ""}
        )
        if not isinstance(existing_items_auto, dict) or not isinstance(existing_items_auto.get("items"), list):
            existing_items_auto = {"items": [], "updatedAt": ""}

        statuses: Dict[str, dict] = {}
        snapshots: List[dict] = []
        fetched_versions = 0
        version_added = 0
        network_enabled = not args.offline
        drafts_payload: dict = existing_drafts
        write_drafts = False
        new_draft_count = 0
        rss_ok = 0
        rss_total = 0
        items_auto_payload: dict = existing_items_auto
        write_items_auto = False
        ai_stats: Optional[dict] = None
        ai_key_present = False

        # --- 版本 ---------------------------------------------------------
        versions_payload: dict = existing_versions
        write_versions = False
        if "versions" in wanted and network_enabled:
            records, version_status = appstore.fetch_versions(client, games, logger.info)
            statuses.update(version_status)
            fetched_versions = len(records)
            merged = appstore.merge_versions(
                existing_versions.get("versions") or [], records, fetched_at=now_iso
            )
            version_added = _count_new_versions(existing_versions.get("versions") or [], merged)
            versions_payload = {"versions": merged, "updatedAt": now_iso}
            write_versions = True
        elif "versions" in wanted and args.offline:
            logger.info("  版本：offline 模式跳过网络")

        # --- 榜单 ---------------------------------------------------------
        charts_payload: dict = existing_charts
        write_charts = False
        if "charts" in wanted and network_enabled:
            snapshots, chart_status = charts_mod.fetch_charts(client, config, logger.info, today_value)
            statuses.update(chart_status)
            charts_payload = charts_mod.merge_charts(
                existing_charts,
                snapshots,
                games,
                today_value,
                history_days=_chart_limit(config, "historyDays", 90),
                top5_days=_chart_limit(config, "top5Days", 90),
                updated_at=now_iso,
            )
            write_charts = True
        elif "charts" in wanted and args.offline:
            logger.info("  榜单：offline 模式跳过网络")

        # --- RSS 线索 -----------------------------------------------------
        if "rss" in wanted and network_enabled:
            new_drafts, rss_status = rss_mod.fetch_drafts(
                client, config, games, logger.info, today_value, now_iso
            )
            statuses.update(rss_status)
            rss_total = len(rss_status)
            rss_ok = sum(1 for value in rss_status.values() if value.get("ok"))
            max_new = int(collector_cfg.get("maxDraftsPerRun") or 40)
            drafts_payload = rss_mod.merge_drafts(
                existing_drafts,
                new_drafts,
                today_value,
                max_new_per_run=max_new,
                fetched_at=now_iso,
            )
            new_draft_count = max(0, len(drafts_payload["drafts"]) - len(existing_drafts["drafts"]))
            write_drafts = True
            logger.info(
                f"  RSS：{rss_ok}/{rss_total} 个源成功，新增线索 {new_draft_count} 条，"
                f"累计 drafts {len(drafts_payload['drafts'])} 条"
            )
        elif "rss" in wanted and args.offline:
            logger.info("  RSS：offline 模式跳过网络")

        # --- AI 提炼（默认关闭；无 key / 失败降级） --------------------------
        if "ai" in wanted:
            if not ai_enabled_flag:
                statuses["ai"] = store.status_entry(
                    False, 0, "跳过：AI 默认关闭（--ai 或 ai.enabled 开启）"
                )
                logger.info("  AI：默认关闭（--ai 可开启，需配置 DeepSeek key）")
            elif args.dry_run:
                statuses["ai"] = store.status_entry(False, 0, "跳过：dry-run 不调用 AI")
                logger.info("  AI：dry-run 跳过调用（不消耗 API）")
            else:
                api_key = ai_mod.resolve_api_key()
                ai_key_present = bool(api_key)
                if not api_key:
                    statuses["ai"] = ai_mod.make_status_entry({}, key_present=False)
                    logger.info("  AI 降级：未配置 key，未调用（drafts 保持 aiStatus=none）")
                else:
                    ai_client = ai_mod.AiClient(
                        api_key=api_key,
                        base_url=str(ai_cfg.get("baseUrl") or ai_mod.DEFAULT_BASE_URL),
                        model=str(ai_cfg.get("model") or ai_mod.DEFAULT_MODEL),
                        temperature=float(ai_cfg.get("temperature", ai_mod.DEFAULT_TEMPERATURE)),
                        timeout=float(collector_cfg.get("timeoutSeconds") or 30),
                        proxy=str(config.get("proxy") or ""),
                        logger=logger.info,
                    )
                    cache = ai_mod.load_cache()
                    known_game_ids = sorted({str(game.get("id")) for game in games if game.get("id")})
                    drafts_payload, new_items, ai_stats, new_cache = ai_mod.enrich_drafts(
                        ai_client,
                        drafts_payload.get("drafts") or [],
                        config,
                        cache,
                        known_game_ids,
                        now_iso,
                        logger.info,
                    )
                    write_drafts = True
                    write_items_auto = True
                    items_auto_payload = ai_mod.merge_items_auto(
                        existing_items_auto, new_items, today_value, updated_at=now_iso
                    )
                    ai_mod.save_cache(new_cache)
                    statuses["ai"] = ai_mod.make_status_entry(ai_stats, key_present=True)
                    logger.info("  AI：" + ai_mod.summarize_stats(ai_stats, True))

        # --- 告警 ---------------------------------------------------------
        alerts_payload: dict = existing_alerts
        new_alert_count = 0
        write_alerts = False
        if "alerts" in wanted:
            chart_alerts: List[dict] = []
            if snapshots:
                chart_alerts = alerts_mod.detect_chart_alerts(
                    previous_chart_state, snapshots, games, today, logger.info
                )
            version_alerts = alerts_mod.detect_version_alerts(
                existing_versions.get("versions") or [],
                versions_payload.get("versions") or [],
                games,
                today,
            )
            candidates = alerts_mod.filter_new_alerts(
                chart_alerts + version_alerts, previous_alert_state
            )
            alerts_payload = alerts_mod.merge_alerts(
                existing_alerts, candidates, today_value, updated_at=now_iso
            )
            new_alert_count = len(candidates)
            write_alerts = True
            if not candidates:
                logger.info("  告警：本轮无新增（基线/无变化/已去重）")
        else:
            candidates = []

        # --- 源状态 -------------------------------------------------------
        status_payload = store.merge_source_status(existing_status, statuses, now_iso)
        # 清理旧版遗留的占位状态：旧 key "rss" 已由 rss_<feedId> 取代
        if "rss" in wanted and network_enabled and rss_total > 0:
            status_payload["sources"].pop("rss", None)

        # --- 写盘（dry-run 不写） ----------------------------------------
        if not args.dry_run:
            if write_versions:
                store.write_json_atomic(store.auto_path("versions.json"), versions_payload)
                logger.info(f"  已写入 versions.json（{len(versions_payload['versions'])} 条）")
            if write_charts:
                store.write_json_atomic(store.auto_path("charts.json"), charts_payload)
                logger.info(f"  已写入 charts.json（latest {len(charts_payload['latest'])} 条）")
            if write_alerts:
                store.write_json_atomic(store.auto_path("alerts.json"), alerts_payload)
                logger.info(f"  已写入 alerts.json（{len(alerts_payload['alerts'])} 条）")
            if write_drafts:
                store.write_json_atomic(store.auto_path("drafts.json"), drafts_payload)
                logger.info(f"  已写入 drafts.json（{len(drafts_payload['drafts'])} 条）")
            if write_items_auto:
                store.write_json_atomic(store.auto_path("items-auto.json"), items_auto_payload)
                logger.info(f"  已写入 items-auto.json（{len(items_auto_payload['items'])} 条）")
            store.write_json_atomic(store.auto_path("source_status.json"), status_payload)
            if write_charts and snapshots:
                state = charts_mod.chart_state_from_snapshots(
                    previous_chart_state, snapshots, today_value, now_iso
                )
                store.save_state("chart_state", state)
            if write_alerts:
                store.save_state(
                    "alert_state",
                    alerts_mod.update_alert_state(previous_alert_state, candidates, today_value),
                )
        elif write_versions and version_added:
            logger.info(f"  [dry-run] 将新增 {version_added} 条版本（不写盘）")
        if args.dry_run and write_drafts and new_draft_count:
            logger.info(f"  [dry-run] 将新增 {new_draft_count} 条线索（不写盘）")

        # --- 摘要 ---------------------------------------------------------
        failed_sources = [
            key for key, value in statuses.items()
            if not value.get("ok") and not str(value.get("error", "")).startswith("跳过")
        ]
        skipped_sources = [
            key for key, value in statuses.items()
            if not value.get("ok") and str(value.get("error", "")).startswith("跳过")
        ]
        success_count = sum(1 for value in statuses.values() if value.get("ok"))
        fail_count = len(failed_sources)
        logger.info("采集摘要：")
        logger.info(
            f"  版本：抓取 {fetched_versions} 条，新增 {version_added} 条，"
            f"累计 {len(versions_payload.get('versions') or [])} 条"
        )
        logger.info(
            f"  榜单：成功快照 {len(snapshots)} 个，latest {len(charts_payload.get('latest') or [])} 条，"
            f"top5 {len(charts_payload.get('top5') or [])} 条，"
            f"rankHistory 覆盖游戏 {len(charts_payload.get('rankHistory') or {})} 款"
        )
        logger.info(
            f"  告警：新增 {new_alert_count} 条，累计 {len(alerts_payload.get('alerts') or [])} 条"
        )
        logger.info(
            f"  线索：RSS {rss_ok}/{rss_total} 个源成功，新增 {new_draft_count} 条，"
            f"累计 drafts {len(drafts_payload.get('drafts') or [])} 条；"
            f"AI 情报累计 {len(items_auto_payload.get('items') or [])} 条"
        )
        if "ai" in wanted and ai_stats is not None:
            logger.info("  AI：" + ai_mod.summarize_stats(ai_stats, ai_key_present))
        logger.info(f"  源：成功 {success_count}，失败 {fail_count}，跳过 {len(skipped_sources)}")
        for key in sorted(failed_sources):
            logger.info(f"    失败 {key}：{statuses[key].get('error', '')}")
        for key in sorted(skipped_sources):
            logger.info(f"    跳过 {key}：{statuses[key].get('error', '')}")
        logger.info(f"  跟踪游戏 {len(games)} 款；日期 {today}；"
                    f"榜单国家 {'/'.join((config.get('charts') or {}).get('countries', []))}")

        # --- 构建 ---------------------------------------------------------
        build_code = 0
        if args.dry_run:
            logger.info("  构建：dry-run 跳过")
        elif args.no_build:
            logger.info("  构建：--no-build 跳过")
        elif args.offline and not args.no_build:
            build_code, output = run_build(logger)
            if build_code != 0:
                logger.info("  构建失败：")
                for line in output.splitlines()[:30]:
                    logger.info(f"    {line}")
        else:
            build_code, output = run_build(logger)
            if build_code == 0:
                for line in output.splitlines():
                    logger.info(f"  {line}")
            else:
                logger.info("  构建失败：")
                for line in output.splitlines()[:30]:
                    logger.info(f"    {line}")

        if build_code != 0:
            logger.info("退出码 2（构建/校验失败，采集数据已保留）")
            return 2

        exit_code = 0 if (success_count > 0 or args.offline) else 1
        if not network_enabled:
            exit_code = 0
        logger.info(f"退出码 {exit_code}")
        return exit_code
    finally:
        logger.close()


def main(argv: Optional[Sequence[str]] = None) -> int:
    args_for_error: Optional[Sequence[str]] = argv
    try:
        return run(argv)
    except SystemExit:
        raise
    except Exception as exc:  # 兜底：不把堆栈直接甩给用户（--ci 静默）
        ci = "--ci" in (args_for_error if args_for_error is not None else sys.argv[1:])
        verbose = "--verbose" in (args_for_error if args_for_error is not None else sys.argv[1:])
        print(f"采集异常：{type(exc).__name__}: {exc}")
        if verbose and not ci:
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
