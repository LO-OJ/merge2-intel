/* 周报 */
(function () {
  "use strict";
  var App = (window.App = window.App || {});
  App.views = App.views || {};
  var h = App.h;
  var icon = App.icon;
  var fmt = App.fmt;

  function sortedDigests() {
    return (App.KB.digests || []).slice().sort(function (a, b) {
      return String(b.start || "").localeCompare(String(a.start || ""));
    });
  }

  function fallbackDigest() {
    var items = (App.KB.items || []).filter(function (item) {
      var d = App.daysSince(item.publishedAt);
      return d !== null && d >= 0 && d <= 7;
    });
    var top = items.slice().sort(function (a, b) { return (b.importance || 0) - (a.importance || 0); }).slice(0, 6);
    if (!top.length) top = (App.KB.items || []).slice(0, 6);
    var dims = {};
    top.forEach(function (item) { (item.dimensions || []).forEach(function (dim) { dims[dim] = (dims[dim] || 0) + 1; }); });
    var dimText = Object.keys(dims).map(function (dim) { return App.dimMeta(dim).label + " " + dims[dim]; }).join("、");
    var actions = [];
    var playbook = (App.KB.playbook || [])[0];
    if (playbook && playbook.checklist) actions = playbook.checklist.slice(0, 3);
    return {
      id: "auto-current",
      week: "本周",
      start: App.todayISO(),
      end: App.todayISO(),
      headline: "本周整理 " + top.length + " 条重点情报",
      overview: "（自动汇总）本周情报集中在 " + (dimText || "—") + "。这是根据入库情报自动生成的摘要；还没有手写周报时显示此版本。",
      topItemIds: top.map(function (item) { return item.id; }),
      actions: actions,
      generatedAt: new Date().toISOString()
    };
  }

  function periodText(digest) {
    if (!digest.start && !digest.end) return digest.week || "";
    return (digest.start || "") + " 至 " + (digest.end || "");
  }

  function digestMarkdown(digest) {
    var lines = [];
    lines.push("# 二合情报周报 · " + (digest.week || digest.id));
    lines.push("");
    lines.push("> " + periodText(digest));
    lines.push("");
    lines.push("## " + (digest.headline || "本周结论"));
    lines.push("");
    lines.push(digest.overview || "");
    lines.push("");
    var items = (digest.topItemIds || []).map(App.itemById).filter(Boolean);
    if (items.length) {
      lines.push("## 重点情报");
      lines.push("");
      items.forEach(function (item) {
        lines.push("### " + item.title);
        lines.push("");
        lines.push("- " + fmt.full(item.publishedAt) + " · " + (item.sourceName || item.sourceId));
        lines.push("");
        lines.push(item.summary || "");
        lines.push("");
        if (item.takeaway) lines.push("**可借鉴动作：** " + item.takeaway);
        lines.push("");
        if (item.url) lines.push("[原文](" + item.url + ")");
        lines.push("");
      });
    }
    if (digest.actions && digest.actions.length) {
      lines.push("## 下周行动");
      lines.push("");
      digest.actions.forEach(function (action) { lines.push("- [ ] " + action); });
      lines.push("");
    }
    return lines.join("\n");
  }

  function actionsPanel(digest) {
    var panel = h("div", { class: "panel" }, [App.comp.sectionTitle("行动建议", "勾选保存在本机")]);
    (digest.actions || []).forEach(function (text, index) {
      var key = "digest-" + digest.id + "-action-" + index;
      var checked = App.store.isChecked(key);
      var row = h("label", { class: "check-row" + (checked ? " is-checked" : "") }, [
        h("input", { type: "checkbox", checked: checked, on: { change: function () {
          var on = App.store.toggleCheck(key);
          row.classList.toggle("is-checked", on);
        } } }),
        h("span", null, text)
      ]);
      panel.appendChild(row);
    });
    return panel;
  }

  function render(route) {
    var digests = sortedDigests();
    var digest = null;
    if (route.id) {
      digest = digests.filter(function (item) { return item.id === route.id; })[0];
    }
    if (!digest) digest = digests[0] || fallbackDigest();
    var fragment = document.createDocumentFragment();
    fragment.appendChild(App.comp.pageHead("周报", "把一周的情报、版本与榜单变化压成一页，直接带到周会。", [
      h("button", { class: "btn btn-ghost", type: "button", on: { click: function () {
        App.download("二合周报-" + (digest.week || digest.id) + ".md", digestMarkdown(digest), "text/markdown;charset=utf-8");
      } } }, [icon("download"), "导出 Markdown"])
    ]));

    if (digests.length) {
      var archive = h("div", { class: "tabs" });
      digests.forEach(function (item) {
        archive.appendChild(h("button", {
          class: "tab" + (item.id === digest.id ? " is-active" : ""),
          type: "button",
          on: { click: function () { App.go("digest", item.id); } }
        }, item.week || item.id));
      });
      fragment.appendChild(archive);
    }

    var article = h("article", { class: "digest-article" }, [
      h("p", { class: "eyebrow" }, "WEEKLY DIGEST · " + periodText(digest)),
      h("h1", null, digest.headline || "本周情报"),
      h("p", { class: "digest-overview" }, digest.overview || ""),
      digest.generatedAt ? h("p", { class: "muted small" }, "生成于 " + fmt.full(digest.generatedAt) + " · 自动摘要请核对原文") : null
    ]);
    fragment.appendChild(article);

    var topItems = (digest.topItemIds || []).map(App.itemById).filter(Boolean);
    var main = h("div", { class: "two-col digest-columns" });
    var left = h("div", null, [
      h("div", { class: "panel" }, [
        App.comp.sectionTitle("重点情报", topItems.length + " 条"),
        topItems.length ? h("div", { class: "item-list" }, topItems.map(function (item) { return App.comp.itemCard(item, { compact: true }); })) : h("p", { class: "muted" }, "本周还没有重点情报。")
      ])
    ]);
    var right = h("div", null, [actionsPanel(digest)]);

    var weekVersions = (App.KB.versions || []).filter(function (version) {
      return version.releasedAt && version.releasedAt >= (digest.start || "") && version.releasedAt <= (digest.end || "9999-12-31");
    }).slice(0, 8);
    if (weekVersions.length) {
      var versionPanel = h("div", { class: "panel" }, [App.comp.sectionTitle("本周版本")]);
      weekVersions.forEach(function (version) {
        var game = App.gameById(version.gameId);
        versionPanel.appendChild(h("a", { class: "version-row", href: "#/game/" + version.gameId }, [
          h("span", { class: "version-date" }, fmt.date(version.releasedAt)),
          h("span", { class: "version-main" }, [
            h("strong", null, game ? (game.nameZh || game.name) : version.gameId),
            h("span", null, "v" + version.version + " · " + App.storeLabel(version.store))
          ]),
          icon("arrow-right", "icon-xs")
        ]));
      });
      right.appendChild(versionPanel);
    }

    var weekAlerts = (App.KB.alerts || []).filter(function (alert) {
      return alert.date && alert.date >= (digest.start || "") && alert.date <= (digest.end || "9999-12-31");
    });
    if (weekAlerts.length) {
      var alertPanel = h("div", { class: "panel" }, [App.comp.sectionTitle("本周雷达")]);
      weekAlerts.slice(0, 5).forEach(function (alert) {
        alertPanel.appendChild(h("a", { class: "related-row", href: "#/radar" }, [
          h("span", { class: "related-date" }, App.alertLabel(alert.type)),
          h("span", { class: "related-title" }, alert.summary || ""),
          icon("arrow-right", "icon-xs")
        ]));
      });
      right.appendChild(alertPanel);
    }

    main.appendChild(left);
    main.appendChild(right);
    fragment.appendChild(main);

    if (!digests.length) {
      fragment.appendChild(h("p", { class: "muted" }, "手写周报会出现在这里；当前为自动汇总版。"));
    }
    return fragment;
  }

  App.views.digest = { render: render, title: "周报" };
})();
