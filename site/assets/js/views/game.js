/* 游戏档案 */
(function () {
  "use strict";
  var App = (window.App = window.App || {});
  App.views = App.views || {};
  var h = App.h;
  var icon = App.icon;
  var fmt = App.fmt;

  var MATRIX_LABELS = {
    energy: "体力/行动",
    events: "活动类型",
    pass: "通行证/订阅",
    offers: "礼包结构",
    ads: "广告变现",
    collab: "联动",
    cadence: "更新节奏"
  };

  function listBlock(title, values, iconName) {
    var box = h("div", { class: "fact-card" }, [
      h("h3", null, [iconName ? icon(iconName, "icon-sm") : null, title])
    ]);
    if (!values || !values.length) {
      box.appendChild(h("p", { class: "muted" }, "待补充"));
    } else {
      box.appendChild(h("div", { class: "chip-row" }, values.map(function (value) {
        return App.comp.chip(value, { cls: "chip-soft" });
      })));
    }
    return box;
  }

  function textBlock(title, text, iconName) {
    return h("div", { class: "fact-card" }, [
      h("h3", null, [iconName ? icon(iconName, "icon-sm") : null, title]),
      h("p", { class: text ? "" : "muted" }, text || "待补充")
    ]);
  }

  function storeLinks(game) {
    var stores = game.stores || {};
    var row = h("div", { class: "chip-row" });
    Object.keys(stores).forEach(function (store) {
      var a = h("a", { class: "chip chip-link", href: "https://apps.apple.com/" + store + "/app/id" + stores[store], target: "_blank", rel: "noopener noreferrer" }, [icon("external", "icon-xs"), App.storeLabel(store) + " App Store"]);
      row.appendChild(a);
    });
    return row;
  }

  function rankPanel(game) {
    var panel = h("div", { class: "panel" }, [
      App.comp.sectionTitle("榜单位置", "美国/中国/日本 App Store，每日快照", h("a", { class: "text-link", href: "#/radar" }, ["爆款雷达 ", icon("arrow-right", "icon-xs")])),
      h("p", { class: "muted" }, "加载榜单数据…")
    ]);
    if (App.loadCharts) {
      App.loadCharts(function () {
        var body = panel;
        body.innerHTML = "";
        body.appendChild(App.comp.sectionTitle("榜单位置", "美国/中国/日本 App Store，每日快照", h("a", { class: "text-link", href: "#/radar" }, ["爆款雷达 ", icon("arrow-right", "icon-xs")])));
        var charts = App.charts || {};
        var history = (charts.rankHistory || {})[game.id] || {};
        var countries = Object.keys(history);
        if (!countries.length) {
          body.appendChild(h("p", { class: "muted" }, "这款游戏还没有进入监控榜单记录。采集脚本每日运行后，会从第二天开始显示排名变化。"));
          return;
        }
        countries.forEach(function (country) {
          var card = h("div", { class: "rank-card" }, [h("h3", null, App.countryLabel(country))]);
          Object.keys(history[country]).forEach(function (kindId) {
            var entries = history[country][kindId] || [];
            if (!entries.length) return;
            var latest = entries[entries.length - 1];
            var previous = entries.length > 1 ? entries[entries.length - 2] : null;
            var delta = previous ? previous[1] - latest[1] : null;
            var row = h("div", { class: "rank-row" }, [
              h("span", { class: "rank-kind" }, kindLabel(kindId)),
              h("strong", { class: "rank-value" }, "#" + latest[1]),
              delta === null ? h("span", { class: "rank-new" }, "新") :
                h("span", { class: "rank-delta " + (delta > 0 ? "up" : delta < 0 ? "down" : "flat") }, delta === 0 ? "—" : (delta > 0 ? "↑" : "↓") + Math.abs(delta)),
              App.comp.sparkline(entries.map(function (entry) { return entry[1]; }), { width: 96, height: 28, label: "排名趋势" })
            ]);
            card.appendChild(row);
          });
          body.appendChild(card);
        });
      });
    }
    return panel;
  }

  function kindLabel(kindId) {
    return {
      "overall-grossing": "综合畅销",
      "overall-free": "综合免费",
      "puzzle-grossing": "Puzzle 畅销",
      "casual-grossing": "Casual 畅销"
    }[kindId] || kindId;
  }

  function versionTimeline(game) {
    var versions = (App.KB.versions || []).filter(function (version) { return version.gameId === game.id; });
    versions.sort(function (a, b) { return String(b.releasedAt || "").localeCompare(String(a.releasedAt || "")); });
    var box = h("div", { class: "panel" }, [
      App.comp.sectionTitle("版本动态", "最近 " + Math.min(versions.length, 8) + " 个版本", h("a", { class: "text-link", href: "#/versions" }, ["全部版本 ", icon("arrow-right", "icon-xs")]))
    ]);
    if (!versions.length) {
      box.appendChild(h("p", { class: "muted" }, "还没有采集到版本记录。运行「更新情报.bat」或等待每日自动更新。"));
      return box;
    }
    var timeline = h("div", { class: "timeline" });
    versions.slice(0, 8).forEach(function (version) {
      var notes = version.notes || "";
      var row = h("article", { class: "timeline-item" }, [
        h("div", { class: "timeline-dot" }),
        h("div", { class: "timeline-body" }, [
          h("div", { class: "timeline-head" }, [
            h("strong", null, "v" + version.version),
            h("span", { class: "badge badge-soft" }, App.storeLabel(version.store)),
            h("span", { class: "timeline-date" }, version.releasedAt ? fmt.full(version.releasedAt) : "—")
          ]),
          version.highlights && version.highlights.length ? h("div", { class: "chip-row" }, version.highlights.slice(0, 4).map(function (highlight) {
            return App.comp.chip(highlight.text, { cls: "chip-xs chip-soft" });
          })) : null,
          notes ? h("details", { class: "version-notes" }, [
            h("summary", null, "更新说明"),
            h("p", null, notes)
          ]) : null,
          version.notesUrl ? App.comp.sourceLink(version.notesUrl, "商店页") : null
        ])
      ]);
      timeline.appendChild(row);
    });
    box.appendChild(timeline);
    return box;
  }

  function render(route) {
    var game = App.gameById(route.id);
    var fragment = document.createDocumentFragment();
    if (!game) {
      fragment.appendChild(App.comp.emptyState("找不到这款游戏", "可能链接有误。", "回到游戏库", function () { App.go("games"); }));
      return fragment;
    }
    var version = App.latestVersion(game);
    var related = (App.KB.items || []).filter(function (item) {
      return (item.gameIds || []).indexOf(game.id) >= 0;
    }).sort(function (a, b) { return String(b.publishedAt || "").localeCompare(String(a.publishedAt || "")); });

    var header = h("header", { class: "game-hero" }, [
      h("div", { class: "game-hero-top" }, [
        App.comp.gameAvatar(game, "xl"),
        h("div", { class: "game-hero-copy" }, [
          h("div", { class: "chip-row" }, [
            h("span", { class: "badge " + (App.ROLES[game.role] || {}).cls }, (App.ROLES[game.role] || {}).label || game.role),
            version ? h("span", { class: "badge badge-soft" }, "最新 v" + version.version + " · " + App.storeLabel(version.store)) : null
          ]),
          h("h1", null, game.nameZh || game.name),
          h("p", { class: "game-hero-sub" }, [game.name, game.publisher].filter(Boolean).join(" · ")),
          h("p", { class: "game-hero-genre" }, game.genre || "")
        ])
      ]),
      h("div", { class: "game-hero-actions" }, [
        storeLinks(pageGame(game)),
        h("a", { class: "btn btn-ghost", href: "#/matrix" }, [icon("grid"), "对比矩阵"]),
        h("a", { class: "btn btn-ghost", href: "#/feed?game=" + game.id }, [icon("feed"), "看 " + related.length + " 条情报"])
      ])
    ]);
    fragment.appendChild(header);

    if (game.positioning) {
      fragment.appendChild(h("blockquote", { class: "positioning" }, game.positioning));
    }

    fragment.appendChild(h("div", { class: "fact-grid two" }, [
      listBlock("核心循环", game.coreLoop, "refresh"),
      listBlock("变现方式", game.monetization, "coins"),
      textBlock("活动/版本节奏", game.eventCadence, "calendar"),
      listBlock("系统亮点", game.notableSystems, "puzzle")
    ]));

    if (game.borrow && game.borrow.length) {
      var borrow = h("div", { class: "panel accent-panel" }, [
        App.comp.sectionTitle("可借鉴点", "从公开信息里提炼，落到我们的活动/系统/数值上"),
        h("ul", { class: "bullet-list borrow-list" }, game.borrow.map(function (text) {
          return h("li", null, [icon("target", "icon-sm"), h("span", null, text)]);
        }))
      ]);
      fragment.appendChild(borrow);
    }

    if (game.risks && game.risks.length) {
      fragment.appendChild(h("div", { class: "panel" }, [
        App.comp.sectionTitle("风险与注意"),
        h("ul", { class: "bullet-list risk-list" }, game.risks.map(function (text) {
          return h("li", null, [icon("alert", "icon-sm"), h("span", null, text)]);
        }))
      ]));
    }

    if (game.matrix && Object.keys(game.matrix).length) {
      var matrix = h("div", { class: "panel" }, [App.comp.sectionTitle("机制速览")]);
      var grid = h("div", { class: "matrix-mini" });
      Object.keys(MATRIX_LABELS).forEach(function (key) {
        if (!game.matrix[key]) return;
        grid.appendChild(h("div", { class: "matrix-mini-cell" }, [
          h("span", null, MATRIX_LABELS[key]),
          h("strong", null, game.matrix[key])
        ]));
      });
      matrix.appendChild(grid);
      fragment.appendChild(matrix);
    }

    fragment.appendChild(rankPanel(game));
    fragment.appendChild(versionTimeline(game));

    var relatedPanel = h("div", { class: "panel" }, [
      App.comp.sectionTitle("相关情报", related.length + " 条", h("a", { class: "text-link", href: "#/feed?game=" + game.id }, ["在情报流查看 ", icon("arrow-right", "icon-xs")]))
    ]);
    if (related.length) {
      var list = h("div", { class: "item-list" });
      related.slice(0, 6).forEach(function (item) { list.appendChild(App.comp.itemCard(item, { compact: true })); });
      relatedPanel.appendChild(list);
    } else {
      relatedPanel.appendChild(h("p", { class: "muted" }, "还没有关联情报。"));
    }
    fragment.appendChild(relatedPanel);

    var noteKey = "game:" + game.id;
    var notePanel = h("div", { class: "panel" }, [
      App.comp.sectionTitle("我的备注", "只保存在本机浏览器，不会进入公开站点"),
      h("textarea", { class: "note-input", rows: 4, placeholder: "这款游戏和我们的差异、值得跟的动作、待验证的判断…", value: App.store.getNote(noteKey) }),
      h("div", { class: "note-actions" }, [
        h("button", { class: "btn btn-soft", type: "button", on: { click: function (event) {
          var area = event.currentTarget.closest(".panel").querySelector("textarea");
          App.store.setNote(noteKey, area.value);
          App.toast("备注已保存");
        } } }, "保存备注")
      ])
    ]);
    fragment.appendChild(notePanel);

    if (game.sourceUrls && game.sourceUrls.length) {
      var src = h("div", { class: "panel" }, [App.comp.sectionTitle("参考来源")]);
      game.sourceUrls.forEach(function (url) {
        var link = App.comp.sourceLink(url, App.host(url) || url);
        if (link) src.appendChild(h("div", { class: "source-row" }, link));
      });
      fragment.appendChild(src);
    }

    return fragment;
  }

  // 仅用于让 storeLinks 读取 stores；保持函数简单
  function pageGame(game) { return game; }

  App.views.game = { render: render, title: "游戏档案" };
})();
