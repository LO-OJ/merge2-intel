/* 设置 */
(function () {
  "use strict";
  var App = (window.App = window.App || {});
  App.views = App.views || {};
  var h = App.h;
  var icon = App.icon;
  var fmt = App.fmt;

  function themeRow() {
    var current = App.store.theme();
    var row = h("div", { class: "segmented" });
    [["auto", "跟随系统"], ["light", "浅色"], ["dark", "深色"]].forEach(function (pair) {
      var btn = h("button", { class: "seg-btn" + (current === pair[0] ? " is-active" : ""), type: "button" }, pair[1]);
      btn.addEventListener("click", function () {
        App.store.setTheme(pair[0]);
        App.comp.applyTheme();
        App.router.refresh();
      });
      row.appendChild(btn);
    });
    return row;
  }

  function render() {
    var meta = App.meta();
    var stats = App.KB.stats || {};
    var counts = App.store.counts();
    var fragment = document.createDocumentFragment();
    fragment.appendChild(App.comp.pageHead("设置", "外观、个人数据与站点信息。"));

    fragment.appendChild(h("div", { class: "panel" }, [
      App.comp.sectionTitle("外观"),
      h("div", { class: "setting-row" }, [h("div", null, [h("strong", null, "主题"), h("p", { class: "muted small" }, "默认跟随系统，也可固定浅色/深色。")]), themeRow()]),
      h("div", { class: "setting-row" }, [
        h("div", null, [h("strong", null, "紧凑密度"), h("p", { class: "muted small" }, "减少卡片留白，适合大屏一次看更多。")]),
        (function () {
          var label = h("label", { class: "switch" });
          var input = h("input", { type: "checkbox", checked: App.store.compact(), on: { change: function () {
            App.store.setCompact(input.checked);
            App.comp.applyTheme();
          } } });
          label.appendChild(input);
          label.appendChild(h("span", { class: "switch-track" }));
          return label;
        })()
      ])
    ]));

    fragment.appendChild(h("div", { class: "panel" }, [
      App.comp.sectionTitle("个人数据", "仅保存在本机浏览器"),
      h("p", { class: "muted" }, "已读 " + counts.read + " 条 · 收藏 " + counts.bookmarks + " 条 · 笔记 " + counts.notes + " 条 · 行动勾选 " + counts.checklist + " 项。"),
      h("div", { class: "button-row" }, [
        h("a", { class: "btn btn-soft", href: "#/notes" }, [icon("bookmark"), "去管理"]),
        h("button", { class: "btn btn-ghost", type: "button", on: { click: function () {
          App.download("二合情报-我的记录-" + App.todayISO() + ".json", App.store.exportJSON(), "application/json;charset=utf-8");
        } } }, [icon("download"), "导出 JSON"])
      ])
    ]));

    fragment.appendChild(h("div", { class: "panel" }, [
      App.comp.sectionTitle("数据与构建"),
      h("div", { class: "kv-list" }, [
        kv("站点", meta.siteName + " / " + meta.siteNameEn),
        kv("构建号", meta.buildId || "—"),
        kv("生成时间", meta.generatedAt ? fmt.full(meta.generatedAt) + " " + String(meta.generatedAt).slice(11, 16) : "—"),
        kv("情报", (stats.items || 0) + " 条（自营 " + (stats.selfGames || 0) + " 款 / 竞品 " + (stats.competitors || 0) + " 款）"),
        kv("来源", (stats.sources || 0) + " 个"),
        kv("版本", (stats.versions || 0) + " 条"),
        kv("待提炼线索", (stats.drafts || 0) + " 条"),
        kv("最近情报日期", stats.lastItemDate || "—")
      ]),
      h("div", { class: "button-row" }, [
        h("button", { class: "btn btn-ghost", type: "button", on: { click: function () { window.location.reload(); } } }, [icon("refresh"), "重新加载"]),
        h("a", { class: "btn btn-ghost", href: "#/sources" }, [icon("globe"), "来源与更新"])
      ])
    ]));

    fragment.appendChild(h("div", { class: "panel" }, [
      App.comp.sectionTitle("更新说明", "本地 / 手机 / GitHub Pages"),
      h("div", { class: "howto" }, [
        h("h3", null, "本地与手机"),
        h("p", null, "双击 启动网站.bat：电脑打开 localhost，手机连同一 Wi-Fi 后访问窗口里打印的局域网地址。")
      ]),
      h("div", { class: "howto" }, [
        h("h3", null, "更新数据"),
        h("p", null, "双击 更新情报.bat（或运行 python tools/collect.py 和 python tools/build.py）。公网版由 GitHub Actions 每天自动更新。")
      ]),
      h("div", { class: "howto" }, [
        h("h3", null, "AI 摘要与密钥"),
        h("p", null, "DeepSeek key 只放在本机 tools/secrets.json 或 GitHub Actions Secret；网页端不读取、不保存 key。")
      ]),
      h("div", { class: "howto" }, [
        h("h3", null, "内容口径"),
        h("p", null, "内容为公开来源整理与摘要，数字可能是第三方估算；做决策前点开原文核对。低置信条目会标“待核实”。")
      ])
    ]));

    fragment.appendChild(h("footer", { class: "about" }, [
      h("p", null, "二合情报站 · Merge-2 Radar v1.0"),
      h("p", { class: "muted small" }, "为 6 款自营二合游戏的活动、系统、上新、商业化与数值参考而建。"),
      meta.disclaimer ? h("p", { class: "muted small" }, meta.disclaimer) : null
    ]));
    return fragment;
  }

  function kv(key, value) {
    return h("div", { class: "kv" }, [h("span", null, key), h("strong", null, value)]);
  }

  App.views.settings = { render: render, title: "设置" };
})();
