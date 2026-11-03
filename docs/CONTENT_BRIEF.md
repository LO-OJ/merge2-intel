# 内容整理任务说明（给内容协作成员）

当前日期：**2026-11-03（Asia/Shanghai）**。所有“最新”内容优先 2026 年，尤其是 2026-09 至 2026-11；旧文只作为产品档案/方法论背景。

## 0. 先读

1. `docs/DATA_SCHEMA.md`（字段、枚举、校验规则）
2. `tools/config.json`（游戏 ID、商店 ID、自动源）
3. `data/curated/games-self.json`、`data/curated/games-watch.json`（已有骨架，只补字段，不改 id/role）
4. `data/curated/sources.json`（来源 ID 白名单）

## 1. 目标

给“二合游戏情报站”准备第一批高质量中文情报库，服务对象是 6 款自营二合游戏的运营/策划/商业化同学，用于：
- 活动优化（节奏、类型、奖励、付费点）
- 系统优化（Merge 核心、体力、订单、元游戏）
- 上新活动（版本、联动、赛季、限时玩法）
- 商业模式（礼包、通行证、广告、订阅）
- 游戏数值（经济来源/消耗、进度节奏、公开基准）

## 2. 写作标准

- **每条情报必须有真实、可打开的公开链接**，并在 `publishedAt` 写发布日期；只拿到搜索摘要、无法确认正文时，`confidence` 降为 `medium/low`，摘要末尾加“（待核实）”。
- **不编造数字、引语、日期、版本号**。数字必须带口径，例如“据 Sensor Tower 估算”“据 AppGrowing 月报”。第三方估算不要写成官方数据。
- 摘要 80–150 字，只写事实与影响；可借鉴动作（takeaway）1–2 条，必须具体：改哪个系统/活动/数值/入口、怎么改。
- 标题用中文，20–34 字，信息量足，不写“震惊”等标题党；英文原标题可放 `titleOriginal`。
- 一条情报只讲一个主题；同一事件不要拆成多条凑数。
- 优先“可操作”的信息：活动结构、付费点、版本节奏、数值变化、买量角度、厂商动作；少放纯融资/纯行业宏观。
- 不确定的游戏机制不要写成事实；用“据…描述”“公开资料显示”。

## 3. 自营 6 款（必须覆盖）

| gameId | 名称 | 厂商 | 商店 |
|---|---|---|---|
| gossip-harbor | 浪漫餐厅 / Gossip Harbor | Microfun / 柠檬微趣 | CN 6472696051 / US 1623318294 |
| kongge-zhijing | 空格之境 | 北京快游互动 | CN 6771265430 |
| flambe | Flambé / 火辣餐厅 | Microfun / 柠檬微趣 | US 6618142292 |
| merge-cooking | Merge Cooking | Happibits / Playdayy 天天玩家 | US 1643509748 |
| feige-meishi | 肥鹅美食街 | 豪腾创想 | CN 6758614459 |
| menghuan-xiaochuzhan | 梦幻消除战 | 广州喜势网络 | CN 6748513887 |

每款至少 3 条情报（版本/活动、榜单/买量、玩法/付费任选），优先 2026 年。
游戏档案要补全：`positioning`、`coreLoop`、`monetization`、`eventCadence`、`notableSystems`、`borrow`、`risks`、`matrix`、`sourceUrls`、`updatedAt`。`matrix` 字段：`energy/events/pass/offers/ads/collab/cadence`，没有公开信息的写“待核实”，不要留空字符串。

## 4. 竞品 10 款

Merge Mansion、Travel Town、Seaside Escape、Merge Gardens、Merge Hotel Empire、Merge County、Merge Survival、Merge Cafe、Merge Restaurant、Tasty Travels（id 见 games-watch.json）。

每款补全档案（可略简），至少 1 条 2026 年情报；优先“版本更新/活动/商业化/榜单”类。
竞品情报 ID 前缀 `cmp-`，自营情报前缀 `self-`。

## 5. 赛道/方法/市场情报（genre 成员）

30–36 条，ID 前缀 `mkt-`，覆盖：

1. 二合赛道规模、增速、头部产品、厂商份额（AppGrowing、Sensor Tower、AppMagic、点点/七麦、白鲸、行业媒体）
2. 头部产品 2026 年的版本/活动/联动/商业化动作
3. 活动设计：赛季、收集、排行榜、剧情章节、装修、限时合成、联动
4. 系统设计：体力、生成器、订单、仓库、地图/建造、收藏册、社交
5. 商业模式：首充、礼包、通行证、订阅、广告、动态定价、piggy bank
6. 数值/经济：来源与消耗、进度门、公开留存/付费基准
7. 买量/素材：题材、创意角度、地区、CPI 公开信息
8. 厂商/资本：收购、融资、新品、榜单异动

每类 3–5 条，避免集中在一个来源。

## 6. 拆解库（genre 成员）

`data/curated/playbook.json` 写 8 章（id 建议）：
`activity-cadence`、`limited-events`、`merge-core`、`meta-game`、`economy`、`monetization`、`onboarding-retention`、`ua-creative`。

每章：`summary` 80–150 字；3–5 条 `principles`（title/detail/evidence）；1–3 个 `cases`（gameId + detail + sourceUrl）；5–8 条 `checklist`（可直接执行的动作）。
`evidence` 引用你写的 `mkt-*` 情报 ID；没有合适证据可空数组，但至少一半原则有证据。

## 7. 周报（genre 成员）

写 2 期：
- `2026-W44`：2026-10-26 至 2026-11-01
- `2026-W45`：2026-11-02 至 2026-11-08（截至 11-03，标注“进行中”）

字段见 DATA_SCHEMA；`topItemIds` 只引用你已写好的 `mkt-*` 条目；`actions` 给 2–3 条具体动作。
不要编造“本周收入”等未公开数字。

## 8. 来源

- 优先用 `data/curated/sources.json` 里已有 ID。
- 需要新增来源时，写入 `data/curated/sources-genre.json`（genre）或 `data/curated/sources-self.json`（self），格式同上，不要改已有来源。
- 可访问性参考：Apple API ✅、AppGrowing ✅、GamesIndustry ✅、17173 ✅、白鲸 ✅、微信公众号文章（用 web_fetch 尝试）、那点事/创业邦/GameLook/游戏葡萄（可能需搜索引擎缓存）。
- PocketGamer/Reddit/Google News/Sensor Tower 直连可能失败；可以引用搜索到的文章标题与链接，但不要假装读过全文；能 fetch 再写细节。

## 9. 产出文件与边界

**self 成员只写：**
- `data/curated/games-self.json`（补字段）
- `data/curated/games-watch.json`（补字段）
- `data/curated/items-self.json`
- `data/curated/items-watch.json`
- `data/curated/sources-self.json`（仅新增来源）

**genre 成员只写：**
- `data/curated/items-market.json`
- `data/curated/playbook.json`
- `data/curated/digests.json`
- `data/curated/sources-genre.json`（仅新增来源）

不要改 `tools/`、`site/`、`data/auto/`、别人的文件。

## 10. 完成前自检

1. JSON 合法（无注释、无尾逗号）。
2. 运行 `python tools/validate.py`；自己文件的错误必须修完；其他成员文件的错误只报告，不要改。
3. 统计：自营/竞品每条 ≥3 条；总 items 数量；日期分布；无法核实条目数。
4. 汇报：写了多少条、覆盖哪些游戏/维度、哪些链接打不开/存疑、哪些内容建议后续人工补。

质量优先于数量。宁可少写 5 条，也不要用模糊来源或编造数字凑数。
