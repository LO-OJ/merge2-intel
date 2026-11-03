/* 总览 */
(function () {
  "use strict";
  var App = (window.App = window.App || {});
  App.views = App.views || {};
  var h = App.h;
  var icon = App.icon;
  var fmt = App.fmt;

  function latestVersion(game) {
    var stores = game.latestVersion || {};
    var order = ["cn", "us", "jp"];
    for (var i = 0; i < order.length; i++) {
      if (stores[order[i]]) return stores[order[i]];
    }
    var keys = Object.keys(stores);
    return keys.length ? stores[keys[0]] : null;
  }

  function recentAlerts(days) {
    return (App.KB.alerts || []).filter(function (alert) {
      var d = App.daysSince(alert.date);
      return d !== null && d >= 0 && d <= days;
    });
  }

  function actionsForHome() {
    var digests = (App.KB.digests || []).slice().sort(function (a, b) {
      return String(b.start || "").localeCompare(String(a.start || ""));
    });
    for (var i = 0; i < digests.length; i++) {
      if (digests[i].actions && digests[i].actions.length) {
        return { source: "周报 · " + digests[i].id, actions: digests[i].actions, prefix: "digest-" + digests[i].id + "-" };
      }
    }
    var playbook = (App.KB.playbook || [])[0];
    if (playbook && playbook.checklist && playbook.checklist.length) {
      return { source: "拆解库 · " + playbook.title, actions: playbook.checklist.slice(0, 4), prefix: "pb-" + playbook.id + "-" };
    }
    return null;
  }

  function render() {
    var meta = App.meta();
    var items = (App.KB.items || []).slice().sort(function (a, b) {
      return String(b.publishedAt || "").localeCompare(String(a.publishedAt || "")) ||
        (b.importance || 0) - (a.importance || 0);
    });
    var games = App.sortGames(App.KB.games || []);
    var selfGames = games.filter(function (g) { return g.role === "self"; });
    var weekItems = items.filter(function (item) { var d = App.daysSince(item.publishedAt); return d !== null && d >= 0 && d <= 7; });
    var topItems = items.filter(function (item) { return item.importance >= 2; }).slice(0, 6);
    if (!topItems.length) topItems = items.slice(0, 6);
    var alerts = recentAlerts(14);
    var fragment = document.createDocumentFragment();

    /* hero */
    var hero = h("section", { class: "hero" }, [
      h("div", { class: "hero-copy" }, [
        h("p", { class: "eyebrow" }, "MERGE-2 INTELLIGENCE"),
        h("h1", null, ["把全网的二合信号，", h("br"), "变成能落地的动作。"]),
        h("p", { class: "hero-sub" }, "自营 6 款 · 竞品 10 款 · App Store 版本与榜单每日更新；活动、系统、上新、商业化、数值，一页找到参考。"),
        h("div", { class: "hero-actions" }, [
          h("a", { class: "btn btn-primary", href: "#/feed" }, [icon("feed"), "看情报流"]),
          h("a", { class: "btn btn-ghost", href: "#/radar" }, [icon("radar"), "打开爆款雷达"]),
          h("a", { class: "btn btn-ghost", href: "#/playbook" }, [icon("layers"), "拆解库"])
        ])
      ]),
      h("div", { class: "hero-stats" }, [
        h("div", { class: "hero-stat" }, [h("strong", null, String(items.length)), h("span", null, "条情报")]),
        h("div", { class: "hero-stat" }, [h("strong", null, String(weekItems.length)), h("span", null, "本周新增")]),
        h("div", { class: "hero-stat" }, [h("strong", null, String(selfGames.length)), h("span", null, "自营游戏")]),
        h("div", { class: "hero-stat" }, [h("strong", null, String(alerts.length)), h("span", null, "近期雷达")])
      ])
    ]);
    fragment.appendChild(hero);

    if (alerts.length) {
      var topAlert = alerts[0];
      var banner = h("a", { class: "alert-banner", href: "#/radar" }, [
        icon("bell", "alert-icon"),
        h("div", null, [
          h("strong", null, "爆款雷达：" + App.alertLabel(topAlert.type)),
          h("span", null, topAlert.summary || (topAlert.name + " 第 " + topAlert.rank + " 名"))
        ]),
        h("span", { class: "alert-more" }, ["查看全部 ", icon("arrow-right", "icon-xs")])
      ]);
      fragment.appendChild(banner);
    }

    /* self games */
    var selfSection = h("section", { class: "section" }, [
      App.comp.sectionTitle("自营游戏", "6 款在运营产品的最新版本、情报量与关注重点", h("a", { class: "text-link", href: "#/games" }, ["全部游戏 ", icon("arrow-right", "icon-xs")])),
      h("div", { class: "game-grid" }, selfGames.map(function (game) {
        var version = latestVersion(game);
        var card = h("a", { class: "game-card", href: "#/game/" + game.id }, [
          h("div", { class: "game-card-head" }, [
            App.comp.gameAvatar(game, "md"),
            h("div", { class: "game-card-title" }, [
              h("strong", null, game.nameZh || game.name),
              h("span", null, game.publisher || "")
            ]),
            h("span", { class: "badge role-self" }, "自营")
          ]),
          h("p", { class: "game-position" }, game.positioning || game.genre || "档案待补充"),
          h("div", { class: "game-card-meta" }, [
            h("span", null, [icon("tag", "icon-xs"), version ? "v" + version.version : "版本待采集"]),
            h("span", null, [icon("feed", "icon-xs"), (game.itemCount || 0) + " 条情报"])
          ]),
          (game.selfFocus && game.selfFocus.length) ? h("div", { class: "chip-row" }, game.selfFocus.slice(0, 3).map(function (focus) {
            return App.comp.chip(focus, { cls: "chip-soft chip-xs" });
          })) : null
        ]);
        return card;
      }))
    ]);
    fragment.appendChild(selfSection);

    /* must read + side */
    var mustRead = h("section", { class: "section" }, [
      App.comp.sectionTitle("本周必看", "按重要度与新鲜度排序，点开即可记笔记", h("a", { class: "text-link", href: "#/feed?importance=2" }, ["更多 ", icon("arrow-right", "icon-xs")])),
      h("div", { class: "item-list" }, topItems.map(function (item) { return App.comp.itemCard(item); }))
    ]);

    var side = h("aside", { class: "side-column" }, [
      h("div", { class: "panel" }, [
        App.comp.sectionTitle("最新版本", "", h("a", { class: "text-link", href: "#/versions" }, ["全部", icon("arrow-right", "icon-xs")])),
        h("div", { class: "version-list compact" }, (App.KB.versions || []).slice(0, 6).map(function (version) {
          var game = App.gameById(version.gameId);
          return h("a", { class: "version-row", href: "#/game/" + version.gameId }, [
            h("span", { class: "version-date" }, fmt.date(version.releasedAt)),
            h("span", { class: "version-main" }, [
              h("strong", null, game ? (game.nameZh || game.name) : version.gameId),
              h("span", null, "v" + version.version + " · " + App.storeLabel(version.store))
            ]),
            icon("chevron-down", "icon-xs version-chevron")
          ]);
        }))
      ]),
      h("div", { class: "panel" }, [
        App.comp.sectionTitle("按维度找参考", "", h("a", { class: "text-link", href: "#/feed" }, ["全部", icon("arrow-right", "icon-xs")])),
        h("div", { class: "dim-list" }, App.DIMS.filter(function (dim) {
          return ["activity", "system", "launch", "monetization", "economy", "market"].indexOf(dim.id) >= 0;
        }).map(function (dim) {
          var count = (App.KB.stats && App.KB.stats.byDimension && App.KB.stats.byDimension[dim.id]) || 0;
          return h("a", { class: "dim-row", href: "#/feed?dim=" + dim.id }, [
            h("span", { class: "dim-dot dim-" + dim.id }),
            h("span", null, dim.label),
            h("span", { class: "dim-count" }, count + " 条")
          ]);
        }))
      ])
    ]);

    var actions = actionsForHome();
    if (actions) {
      var checklist = h("div", { class: "checklist" });
      actions.actions.forEach(function (text, index) {
        var key = actions.prefix + index;
        var checked = App.store.isChecked(key);
        var row = h("label", { class: "check-row" + (checked ? " is-checked" : "") }, [
          h("input", { type: "checkbox", checked: checked, on: { change: function () {
            var on = App.store.toggleCheck(key);
            row.classList.toggle("is-checked", on);
          } } }),
          h("span", null, text)
        ]);
        checklist.appendChild(row);
      });
      side.appendChild(h("div", { class: "panel" }, [
        App.comp.sectionTitle("行动清单", actions.source, h("a", { class: "text-link", href: "#/notes" }, ["我的记录", icon("arrow-right", "icon-xs")])),
        checklist
      ]));
    }

    fragment.appendChild(h("div", { class: "two-col" }, [mustRead, side]));

    /* footer note */
    fragment.appendChild(h("section", { class: "section" }, [
      h("div", { class: "data-note" }, [
        icon("info", "icon-sm"),
        h("p", null, [
          meta.disclaimer || "内容来自公开渠道整理，决策前请核对原文。",
          h("br"),
          "当前构建：" + (meta.buildId || "—") + " · 数据更新：" + (meta.dataUpdatedAt ? fmt.full(meta.dataUpdatedAt) : "待采集") + " · 情报 " + items.length + " 条"
        ])
      ])
    ]));

    return fragment;
  }

  App.views.home = { render: render, title: "总览" };
})();
