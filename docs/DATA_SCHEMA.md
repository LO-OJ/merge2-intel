# 数据规范（v1）

本文件是站点、采集脚本、内容整理共同遵守的契约。所有数据文件均为 UTF-8 JSON（不带 BOM），日期统一用 `YYYY-MM-DD`，时间戳用 ISO 8601（带 `+08:00` 或 `Z`）。

## 1. 目录与合并规则

```
data/curated/*.json   # 人工/编辑整理，可多文件，按顶层 key 合并
data/auto/*.json      # 采集脚本写入，不要手工改
```

`tools/build.py` 会读取 `data/curated/` 下所有 `.json`，把以下顶层数组按顺序合并：

- `games` → 游戏档案
- `items` → 情报条目
- `sources` → 来源目录
- `playbook` → 拆解章节
- `digests` → 周报
- `versions` → 版本种子（可选）

以及可选的顶层对象 `meta`（浅合并）。合并时按 `id` 去重：重复 id 视为构建错误。

## 2. 枚举

- 游戏角色 `role`：`self`（自营）/ `competitor`（竞品）/ `watch`（观察）
- 情报维度 `dimensions`：
  - `activity` 活动运营
  - `system` 系统设计
  - `launch` 新活动/上新
  - `monetization` 商业模式
  - `economy` 数值/经济
  - `market` 市场/榜单
  - `ua` 买量/素材
  - `publisher` 厂商动态
  - `version` 版本更新
- 重要度 `importance`：`1` 一般 / `2` 值得看 / `3` 重点
- 置信度 `confidence`：`high` / `medium` / `low`
- 摘要来源 `summaryBy`：`editor`（编辑整理）/ `ai`（模型提炼，需人工复核）
- 商店 `store`：`cn` / `us` / `jp` / `kr` / `hk` / `tw`（当前采集用 cn/us）
- 日期精度 `datePrecision`：`day`（默认）/ `month` / `year`

## 3. Game 游戏档案

```json
{
  "id": "gossip-harbor",
  "name": "Gossip Harbor",
  "nameZh": "浪漫餐厅",
  "aliases": ["绯闻港口"],
  "publisher": "Microfun / 柠檬微趣",
  "country": "CN",
  "role": "self",
  "genre": "剧情向二合 · 餐厅装修",
  "stores": { "cn": "6472696051", "us": "1623318294" },
  "positioning": "一句话定位",
  "coreLoop": ["合成", "订单", "装修", "剧情"],
  "monetization": ["体力", "礼包", "通行证", "广告"],
  "eventCadence": "活动/版本节奏描述",
  "notableSystems": ["系统亮点"],
  "borrow": ["可以借鉴的具体动作"],
  "risks": ["可能的坑/风险"],
  "matrix": {
    "energy": "体力机制",
    "events": "活动类型",
    "pass": "通行证/订阅",
    "offers": "礼包结构",
    "ads": "广告变现",
    "collab": "联动情况",
    "cadence": "更新节奏"
  },
  "tags": ["剧情", "餐厅", "二合"],
  "color": "#E4572E",
  "logoText": "GH",
  "selfFocus": ["活动节奏", "付费结构"],
  "sourceUrls": ["https://..."],
  "updatedAt": "2026-11-03"
}
```

必填：`id`、`name`、`publisher`、`role`。`stores` 必须是 `{商店: appId 字符串}`。没有的商店不要编造。
自营 6 款：`gossip-harbor`、`kongge-zhijing`、`flambe`、`merge-cooking`、`feige-meishi`、`menghuan-xiaochuzhan`。
竞品 10 款见 `data/curated/games-watch.json`。

## 4. Item 情报条目

```json
{
  "id": "self-0001",
  "title": "中文标题（不以句号结尾）",
  "titleOriginal": "Original English title (optional)",
  "summary": "80–150 字中文摘要，只陈述原文/公开资料能支撑的事实。",
  "takeaway": "1–2 条可执行动作：改哪个活动/系统/数值/入口，怎么改。",
  "dimensions": ["activity", "monetization"],
  "gameIds": ["gossip-harbor"],
  "sourceId": "appgrowing",
  "url": "https://...",
  "publishedAt": "2026-10-16",
  "datePrecision": "day",
  "importance": 2,
  "confidence": "high",
  "summaryBy": "editor",
  "tags": ["活动节奏", "通行证"],
  "createdAt": "2026-11-03"
}
```

必填：`id`、`title`、`summary`、`takeaway`、`dimensions`（至少 1 个）、`sourceId`、`url`（http/https）、`publishedAt`、`importance`、`confidence`、`summaryBy`。
`gameIds` 可以为空（纯市场/方法论情报）。`sourceId` 必须存在于来源目录。
**禁止**编造数字、日期、引语；数字必须在摘要里带口径（如“据 Sensor Tower 估算”）。
低置信或未核实的内容：`confidence: "low"`，并在摘要末尾加“（待核实）”。

## 5. Source 来源

```json
{
  "id": "appgrowing",
  "name": "AppGrowing 国际版",
  "type": "数据/买量",
  "lang": "zh",
  "region": "中国/全球",
  "url": "https://appgrowing.net/blog/",
  "feed": "https://appgrowing.net/blog/feed/",
  "auto": true,
  "note": "一句话说明"
}
```

必填：`id`、`name`、`type`、`url`、`auto`。`auto` 表示当前网络下脚本能否自动抓取。

## 6. Playbook 拆解章节

```json
{
  "id": "activity-cadence",
  "title": "活动节奏与生命周期",
  "dimension": "activity",
  "summary": "本章解决什么问题。",
  "principles": [
    {
      "title": "原则标题",
      "detail": "原则解释与做法。",
      "evidence": ["mkt-0001"]
    }
  ],
  "cases": [
    {
      "gameId": "gossip-harbor",
      "detail": "该游戏的具体做法。",
      "sourceUrl": "https://..."
    }
  ],
  "checklist": ["可勾选的行动项 1", "行动项 2"]
}
```

建议 8 章：活动节奏与生命周期、限时活动与联动、Merge 核心系统、任务/剧情/装修元游戏、经济与数值、变现与礼包、新手/留存/推送、买量与素材。
`evidence` 必须是已存在的情报 `id`；不确定就先留空数组。

## 7. Digest 周报

```json
{
  "id": "2026-W45",
  "week": "2026-W45",
  "start": "2026-11-02",
  "end": "2026-11-08",
  "headline": "本周一句话结论",
  "overview": "150–300 字综述。",
  "topItemIds": ["mkt-0001", "self-0003"],
  "actions": ["下周可执行的 1–3 条动作"],
  "generatedAt": "2026-11-03T15:30:00+08:00"
}
```

## 8. 采集自动数据（data/auto）

### versions.json

```json
{
  "versions": [
    {
      "id": "version-gossip-harbor-cn-4.11.0-2026-10-28",
      "gameId": "gossip-harbor",
      "store": "cn",
      "version": "4.11.0",
      "releasedAt": "2026-10-28",
      "notes": "release notes 原文（可截断到 2000 字）",
      "notesUrl": "https://apps.apple.com/cn/app/id6472696051",
      "ratingCount": 12345,
      "averageRating": 4.6,
      "highlights": [
        { "text": "新增限时活动", "type": "launch" }
      ],
      "fetchedAt": "2026-11-03T07:00:00+08:00"
    }
  ],
  "updatedAt": "2026-11-03T07:00:00+08:00"
}
```

### charts.json

```json
{
  "latest": [
    {
      "date": "2026-11-03",
      "country": "us",
      "kindId": "puzzle-grossing",
      "kind": "topgrossingapplications",
      "genre": 7012,
      "label": "Puzzle 畅销",
      "entries": [
        { "rank": 1, "appId": "123", "name": "Royal Match", "publisher": "Dream Games" }
      ]
    }
  ],
  "top5": [
    {
      "date": "2026-11-03",
      "country": "us",
      "kindId": "puzzle-grossing",
      "entries": [{ "rank": 1, "appId": "123", "name": "Royal Match" }]
    }
  ],
  "rankHistory": {
    "gossip-harbor": {
      "us": {
        "puzzle-grossing": [["2026-11-03", 12]]
      }
    }
  },
  "updatedAt": "2026-11-03T07:00:00+08:00"
}
```

- `latest` 只保留最近一次快照（每个国家 × 榜单一条）。
- `top5` 保留最近 90 天每日前 5。
- `rankHistory` 只记录 config 中跟踪游戏的排名。
- 详细历史（前 50 全量）不落盘，避免站点体积过大。

### alerts.json

```json
{
  "alerts": [
    {
      "id": "alert-20261103-us-puzzle-grossing-gossip-harbor-top5",
      "date": "2026-11-03",
      "type": "top5",
      "country": "us",
      "kindId": "puzzle-grossing",
      "gameId": "gossip-harbor",
      "appId": "1623318294",
      "name": "Gossip Harbor",
      "rank": 4,
      "prevRank": 9,
      "confidence": "high",
      "summary": "进入美国 Puzzle 畅销榜第 4。",
      "sourceUrl": "https://apps.apple.com/us/app/id1623318294"
    }
  ],
  "updatedAt": "2026-11-03T07:00:00+08:00"
}
```

`type`：`top5` / `new-entry` / `rank-jump` / `version` / `suspect-hit`。

### drafts.json（线索/待提炼）

```json
{
  "drafts": [
    {
      "id": "draft-20261103-appgrowing-1",
      "title": "原始标题",
      "excerpt": "原文摘要/提要，≤300 字",
      "url": "https://...",
      "sourceId": "appgrowing",
      "publishedAt": "2026-10-16",
      "lang": "zh",
      "fetchedAt": "2026-11-03T07:00:00+08:00",
      "aiStatus": "none" ,
      "relevance": null
    }
  ],
  "updatedAt": "2026-11-03T07:00:00+08:00"
}
```

`aiStatus`：`none` / `enriched` / `rejected`。当 AI 判定相关且字段完整时，采集脚本可把该线索写入 `data/auto/items-auto.json`（同样遵循 Item 规范，`summaryBy: "ai"`），站点自动合并展示。没有 AI key 时保持 `none`。

### source_status.json

```json
{
  "sources": {
    "appgrowing": { "ok": true, "lastRun": "2026-11-03T07:00:00+08:00", "items": 10, "error": "" }
  },
  "updatedAt": "2026-11-03T07:00:00+08:00"
}
```

## 9. 构建输出

`tools/build.py` 生成：

- `site/data/kb.js`：`window.KB = { meta, games, items, sources, playbook, digests, versions, alerts, drafts, sourceStatus, stats }`
- `site/data/charts.js`：`window.KB_CHARTS = { latest, top5, rankHistory, updatedAt }`

站点不直接 fetch JSON（保证 `file://` 可打开），所以必须打包成 JS 赋值。字符串中的 `</` 会被转义为 `<\/`，防止提前结束 `<script>`。

## 10. 校验

`python tools/validate.py` 必须零错误。构建前会自动跑校验，有错误会中止并打印文件/字段。

必查项：
- 必填字段、类型、枚举
- id 唯一（items/games/sources/playbook/digests）
- 引用存在（sourceId、gameIds、evidence、topItemIds）
- 日期格式与 URL 协议
- 摘要/动作非空，长度合理
- 不包含 `<script`、密钥样式字符串
- 至少保留一条自营游戏情报（警告）
