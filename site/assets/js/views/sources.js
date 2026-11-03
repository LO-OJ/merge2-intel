/* 来源与更新 */
(function () {
  "use strict";
  var App = (window.App = window.App || {});
  App.views = App.views || {};
  var h = App.h;
  var icon = App.icon;
  var fmt = App.fmt;

  function statusFor(source) {
    return source.status || null;
  }

  function sourceCard(source) {
    var status = statusFor(source);
    var card = h("article", { class: "source-card" }, [
      h("div", { class: "source-head" }, [
        h("div", null, [h("h3", null, source.name), h("p", { class: "muted small" }, [source.type, source.lang, source.region].filter(Boolean).join(" · "))]),
        h("div", { class: "chip-row" }, [
          source.auto ? h("span", { class: "badge badge-auto" }, "可自动抓取") : h("span", { class: "badge badge-soft" }, "目录/手动"),
          status ? h("span", { class: "badge " + (status.ok ? "badge-ok" : "badge-warn") }, status.ok ? "正常" : "失败") :
            (source.auto ? h("span", { class: "badge badge-soft" }, "未运行") : null)
        ])
      ]),
      source.note ? h("p", { class: "source-note" }, source.note) : null,
      h("div", { class: "source-meta" }, [
        h("span", null, [icon("feed", "icon-xs"), (source.itemCount || 0) + " 条情报"]),
        status && status.lastRun ? h("span", null, [icon("clock", "icon-xs"), "最近 " + fmt.rel(status.lastRun)]) : null,
        status && status.items ? h("span", null, [icon("download", "icon-xs"), "本轮 " + status.items + " 条"]) : null,
        status && status.error ? h("span", { class: "source-error" }, status.error.slice(0, 80)) : null
      ]),
      h("div", { class: "source-links" }, [
        App.comp.sourceLink(source.url, "打开站点"),
        source.feed ? App.comp.sourceLink(source.feed, "RSS") : null
      ])
    ]);
    return card;
  }

  function statsPanel() {
    var meta = App.meta();
    var stats = App.KB.stats || {};
    var charts = App.charts || null;
    var grid = h("div", { class: "stat-grid" }, [
      App.comp.stat("情报", stats.items || 0, "条已入库"),
      App.comp.stat("版本", stats.versions || 0, "条版本记录"),
      App.comp.stat("来源", stats.sources || 0, "个收录"),
      App.comp.stat("线索", stats.drafts || 0, "条待提炼"),
      App.comp.stat("告警", stats.alerts || 0, "条雷达记录"),
      App.comp.stat("构建", meta.buildId || "—", fmt.full(meta.generatedAt))
    ]);
    return h("div", { class: "panel" }, [
      App.comp.sectionTitle("数据状态", "", h("button", { class: "btn btn-ghost btn-sm", type: "button", on: { click: function () { window.location.reload(); } } }, [icon("refresh"), "刷新页面"])),
      grid,
      charts && charts.updatedAt ? h("p", { class: "muted small" }, "榜单最近采集：" + fmt.full(charts.updatedAt)) : h("p", { class: "muted small" }, "榜单尚未采集；运行采集脚本后自动更新。"),
      h("p", { class: "muted small" }, "AI 提炼：" + (meta.aiStatus ? (meta.aiStatus.ok ? "已启用" : "未启用（无 key 或未开启）") : "未配置") + " · Key 只在采集端使用，网页不接触。"),
      meta.disclaimer ? h("p", { class: "muted small" }, meta.disclaimer) : null
    ]);
  }

  function updatePanel() {
    var panel = h("div", { class: "panel" }, [App.comp.sectionTitle("更新方式", "自动层 + 人工补充")]);
    var steps = [
      { title: "本地一键更新", detail: "双击 更新情报.bat，或在项目根目录运行 python tools/collect.py（抓取 App Store 版本与榜单）和 python tools/build.py（生成站点数据）。" },
      { title: "公网自动更新", detail: "GitHub Pages 仓库的 Actions 每天北京时间 07:00 自动运行：采集 → 构建 → 提交 → 发布。也可在 Actions 页面手动 Run workflow。" },
      { title: "补充深度情报", detail: "媒体情报、产品拆解、活动分析由人工/编辑整理写入 data/curated/ 下的 JSON；再跑一次 build 即可。低置信内容会标“待核实”。" },
      { title: "AI 提炼（可选）", detail: "在 tools/secrets.json 填入 DeepSeek key（或 GitHub Actions Secret），采集端会把英文线索翻译/摘要/打标签；key 不会进入网页。" },
      { title: "访问受限的源", detail: "PocketGamer、Reddit、Google News、Google Play 在当前网络不可达；可在 tools/config.json 的 collector.proxy 配置本地代理后扩展。来源目录仍可直接点开。" }
    ];
    steps.forEach(function (step) {
      panel.appendChild(h("div", { class: "howto" }, [
        h("h3", null, step.title),
        h("p", null, step.detail)
      ]));
    });
    return panel;
  }

  function render() {
    var sources = (App.KB.sources || []).slice();
    var groups = {};
    sources.forEach(function (source) {
      var type = source.type || "其他";
      if (!groups[type]) groups[type] = [];
      groups[type].push(source);
    });
    var fragment = document.createDocumentFragment();
    fragment.appendChild(App.comp.pageHead("来源与更新", "自动抓取什么、目录里还有哪些源、数据什么时候更新。"));
    fragment.appendChild(statsPanel());

    var auto = sources.filter(function (source) { return source.auto; }).length;
    var line = h("div", { class: "result-line" }, [
      h("span", null, "共 " + sources.length + " 个来源，其中 " + auto + " 个可在当前网络自动抓取"),
      h("a", { class: "text-link", href: "#/settings" }, ["去设置 ", icon("arrow-right", "icon-xs")])
    ]);
    fragment.appendChild(line);

    Object.keys(groups).sort(function (a, b) { return groups[b].length - groups[a].length; }).forEach(function (type) {
      var section = h("section", { class: "section" }, [
        App.comp.sectionTitle(type, groups[type].length + " 个")
      ]);
      var grid = h("div", { class: "source-grid" });
      groups[type].forEach(function (source) { grid.appendChild(sourceCard(source)); });
      section.appendChild(grid);
      fragment.appendChild(section);
    });

    fragment.appendChild(updatePanel());
    return fragment;
  }

  App.views.sources = { render: render, title: "来源与更新" };
})();
