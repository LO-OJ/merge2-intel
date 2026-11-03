/* 爆款雷达 */
(function () {
  "use strict";
  var App = (window.App = window.App || {});
  App.views = App.views || {};
  var h = App.h;
  var icon = App.icon;
  var fmt = App.fmt;

  function trackedMap() {
    var map = {};
    (App.KB.games || []).forEach(function (game) {
      Object.keys(game.stores || {}).forEach(function (store) {
        map[String(game.stores[store])] = game;
      });
    });
    return map;
  }

  function alertCard(alert) {
    var game = App.gameById(alert.gameId);
    return h("article", { class: "alert-card alert-" + (alert.type || "info") }, [
      h("div", { class: "alert-card-head" }, [
        h("span", { class: "badge alert-type" }, App.alertLabel(alert.type)),
        h("span", { class: "badge badge-soft" }, App.countryLabel(alert.country)),
        h("span", { class: "alert-date" }, fmt.full(alert.date)),
        alert.confidence === "low" ? h("span", { class: "badge badge-warn" }, "低置信") : null
      ]),
      h("h3", null, alert.summary || ((alert.name || "") + " 第 " + alert.rank + " 名")),
      h("div", { class: "alert-card-foot" }, [
        game ? h("a", { class: "text-link", href: "#/game/" + game.id }, ["游戏档案 ", icon("arrow-right", "icon-xs")]) : null,
        alert.sourceUrl ? App.comp.sourceLink(alert.sourceUrl, "App Store") : null,
        alert.prevRank != null && alert.rank != null ? h("span", { class: "muted" }, "上一名次 #" + alert.prevRank + " → #" + alert.rank) : null
      ])
    ]);
  }

  function renderAlerts() {
    var alerts = (App.KB.alerts || []).slice().sort(function (a, b) {
      return String(b.date || "").localeCompare(String(a.date || ""));
    });
    var box = h("section", { class: "section" }, [
      App.comp.sectionTitle("爆款告警", "进前 5、疑似新爆款、排名跃升与重点版本", h("span", { class: "muted" }, alerts.length + " 条"))
    ]);
    if (!alerts.length) {
      box.appendChild(h("div", { class: "panel muted" }, "还没有告警。采集脚本第一次运行只建立榜单基线；之后出现“二合游戏进前 5 / 新面孔 / 跃升”才会记录。"));
      return box;
    }
    var list = h("div", { class: "alert-list" });
    alerts.slice(0, 30).forEach(function (alert) { list.appendChild(alertCard(alert)); });
    box.appendChild(list);
    return box;
  }

  function chartArea() {
    var panel = h("div", { class: "panel chart-panel" }, [
      App.comp.sectionTitle("App Store 榜单", "Top 50 · 每日采集"),
      h("p", { class: "muted" }, "加载榜单数据…")
    ]);
    if (!App.loadCharts) {
      panel.appendChild(h("p", { class: "muted" }, "榜单模块未加载。"));
      return panel;
    }
    App.loadCharts(function (ok) {
      panel.innerHTML = "";
      panel.appendChild(App.comp.sectionTitle("App Store 榜单", "Top 50 · 每日采集"));
      if (!ok || !App.charts || !(App.charts.latest || []).length) {
        panel.appendChild(App.comp.emptyState("还没有榜单数据", "运行采集脚本后，这里会显示 US/CN/JP 的畅销与免费榜。", "看游戏库", function () { App.go("games"); }));
        return;
      }
      renderChartControls(panel);
    });
    return panel;
  }

  function renderChartControls(panel) {
    var charts = App.charts || {};
    var latest = charts.latest || [];
    var countries = [];
    latest.forEach(function (snap) { if (countries.indexOf(snap.country) < 0) countries.push(snap.country); });
    var countryOrder = ["us", "cn", "jp"];
    countries.sort(function (a, b) { return countryOrder.indexOf(a) - countryOrder.indexOf(b); });
    var route = App.route || App.parseRoute(window.location.hash);
    var country = route.params.get("country") || countries[0] || "us";
    var kindId = route.params.get("kind") || "puzzle-grossing";
    var onlyTracked = route.params.get("filter") === "tracked";

    var controls = h("div", { class: "chart-controls" });
    var countryTabs = h("div", { class: "segmented" });
    countries.forEach(function (item) {
      var btn = h("button", { class: "seg-btn" + (item === country ? " is-active" : ""), type: "button" }, App.countryLabel(item));
      btn.addEventListener("click", function () { App.go("radar", "", { country: item, kind: kindId, filter: onlyTracked ? "tracked" : "" }); });
      countryTabs.appendChild(btn);
    });
    controls.appendChild(countryTabs);

    var kinds = [];
    latest.forEach(function (snap) {
      if (snap.country === country && !kinds.some(function (k) { return k.id === snap.kindId; })) {
        kinds.push({ id: snap.kindId, label: snap.label || snap.kindId });
      }
    });
    var select = h("select", { class: "control-select", on: { change: function () {
      App.go("radar", "", { country: country, kind: select.value, filter: onlyTracked ? "tracked" : "" });
    } } });
    kinds.forEach(function (kind) {
      select.appendChild(h("option", { value: kind.id, selected: kind.id === kindId }, kind.label));
    });
    controls.appendChild(select);

    var trackBtn = h("button", { class: "chip" + (onlyTracked ? " is-active" : ""), type: "button" }, "只看跟踪游戏");
    trackBtn.addEventListener("click", function () {
      App.go("radar", "", { country: country, kind: kindId, filter: onlyTracked ? "" : "tracked" });
    });
    controls.appendChild(trackBtn);
    panel.appendChild(controls);

    var snapshot = latest.filter(function (snap) { return snap.country === country && snap.kindId === kindId; })[0];
    if (!snapshot) {
      panel.appendChild(h("p", { class: "muted" }, "该榜单还没有数据。"));
      return;
    }
    panel.appendChild(h("p", { class: "chart-date" }, "采集于 " + fmt.full(snapshot.date) + " · " + (snapshot.label || kindId)));

    var map = trackedMap();
    var tableWrap = h("div", { class: "chart-table-wrap" });
    var table = h("table", { class: "chart-table" });
    table.appendChild(h("thead", null, h("tr", null, [
      h("th", null, "#"), h("th", null, "应用"), h("th", null, "发行商"), h("th", null, "标记"), h("th", null, "变化")
    ])));
    var tbody = h("tbody");
    (snapshot.entries || []).forEach(function (entry) {
      var game = map[String(entry.appId)];
      if (onlyTracked && !game) return;
      var delta = null;
      if (game && charts.rankHistory && charts.rankHistory[game.id]) {
        var history = charts.rankHistory[game.id][country] && charts.rankHistory[game.id][country][kindId];
        if (history && history.length >= 2) {
          var last = history[history.length - 1];
          var prev = history[history.length - 2];
          if (last[0] === snapshot.date) delta = prev[1] - last[1];
        }
      }
      var row = h("tr", { class: game ? "is-tracked" : "" }, [
        h("td", { class: "rank-num" }, entry.rank),
        h("td", { class: "app-name" }, [h("span", null, entry.name || "—"), game ? h("a", { class: "mini-link", href: "#/game/" + game.id }, "档案") : null]),
        h("td", { class: "app-publisher" }, entry.publisher || ""),
        h("td", null, game ? h("span", { class: "badge " + (App.ROLES[game.role] || {}).cls }, (App.ROLES[game.role] || {}).label || game.role) : ""),
        h("td", { class: "rank-change" }, delta == null ? "" : h("span", { class: delta > 0 ? "up" : delta < 0 ? "down" : "flat" }, delta === 0 ? "—" : (delta > 0 ? "↑" : "↓") + Math.abs(delta)))
      ]);
      tbody.appendChild(row);
    });
    table.appendChild(tbody);
    tableWrap.appendChild(table);
    panel.appendChild(tableWrap);
    if (!tbody.children.length) {
      panel.appendChild(h("p", { class: "muted" }, "这个榜单里没有跟踪的游戏。取消“只看跟踪游戏”即可看完整 Top 50。"));
    }
  }

  function trackedOverview() {
    var charts = App.charts || {};
    var history = charts.rankHistory || {};
    var selfGames = App.sortGames(App.KB.games || []).filter(function (game) { return game.role === "self"; });
    var box = h("section", { class: "section" }, [
      App.comp.sectionTitle("自营游戏排名", "各榜单最新名次与趋势", h("a", { class: "text-link", href: "#/radar" }, ["完整榜单"]))
    ]);
    var grid = h("div", { class: "tracked-grid" });
    selfGames.forEach(function (game) {
      var card = h("a", { class: "tracked-card", href: "#/game/" + game.id }, [
        h("div", { class: "tracked-head" }, [App.comp.gameAvatar(game, "sm"), h("strong", null, game.nameZh || game.name)])
      ]);
      var gameHistory = history[game.id] || {};
      var rows = 0;
      Object.keys(gameHistory).forEach(function (country) {
        Object.keys(gameHistory[country]).forEach(function (kindId) {
          var entries = gameHistory[country][kindId] || [];
          if (!entries.length) return;
          var last = entries[entries.length - 1];
          rows += 1;
          card.appendChild(h("div", { class: "tracked-row" }, [
            h("span", null, App.countryLabel(country) + " · " + kindLabel(kindId)),
            h("strong", null, "#" + last[1])
          ]));
        });
      });
      if (!rows) card.appendChild(h("p", { class: "muted" }, "暂无榜单记录"));
      grid.appendChild(card);
    });
    box.appendChild(grid);
    return box;
  }

  function kindLabel(kindId) {
    return {
      "overall-grossing": "综合畅销",
      "overall-free": "综合免费",
      "puzzle-grossing": "Puzzle 畅销",
      "casual-grossing": "Casual 畅销"
    }[kindId] || kindId;
  }

  function render() {
    var fragment = document.createDocumentFragment();
    fragment.appendChild(App.comp.pageHead("爆款雷达", "自动盯 US/CN/JP 的 App Store 榜单：跟踪游戏进前 5、未知二合新面孔、排名跃升都会在这里出现。"));
    fragment.appendChild(renderAlerts());
    fragment.appendChild(chartArea());
    if (App.charts) fragment.appendChild(trackedOverview());
    fragment.appendChild(h("div", { class: "data-note" }, [
      icon("info", "icon-sm"),
      h("p", null, "榜单只覆盖 iOS App Store；Google Play 当前网络不可达。首次运行只建立基线，趋势从第二天开始积累。")
    ]));
    return fragment;
  }

  App.views.radar = { render: render, title: "爆款雷达" };
})();
