/* 版本动态 */
(function () {
  "use strict";
  var App = (window.App = window.App || {});
  App.views = App.views || {};
  var h = App.h;
  var icon = App.icon;
  var fmt = App.fmt;

  function versionCard(version) {
    var game = App.gameById(version.gameId);
    var notes = version.notes || "";
    return h("article", { class: "version-card" }, [
      h("div", { class: "version-card-head" }, [
        game ? h("a", { class: "version-game", href: "#/game/" + game.id }, [App.comp.gameAvatar(game, "sm"), game.nameZh || game.name]) : h("span", null, version.gameId),
        h("span", { class: "badge badge-soft" }, "v" + version.version),
        h("span", { class: "badge badge-soft" }, App.storeLabel(version.store)),
        h("span", { class: "version-date" }, version.releasedAt ? fmt.full(version.releasedAt) : "—")
      ]),
      version.highlights && version.highlights.length ? h("div", { class: "chip-row" }, version.highlights.slice(0, 5).map(function (highlight) {
        return App.comp.chip(highlight.text, { cls: "chip-soft chip-xs" });
      })) : null,
      notes ? h("details", { class: "version-notes" }, [
        h("summary", null, "更新说明"),
        h("p", null, notes)
      ]) : h("p", { class: "muted" }, "商店未提供更新说明。"),
      h("div", { class: "version-card-foot" }, [
        version.notesUrl ? App.comp.sourceLink(version.notesUrl, "商店页") : null,
        game ? h("a", { class: "text-link", href: "#/feed?game=" + game.id }, ["相关情报 ", icon("arrow-right", "icon-xs")]) : null
      ])
    ]);
  }

  function cadenceCards() {
    var versions = App.KB.versions || [];
    var byGame = {};
    versions.forEach(function (version) {
      if (!byGame[version.gameId]) byGame[version.gameId] = [];
      byGame[version.gameId].push(version);
    });
    var rows = [];
    Object.keys(byGame).forEach(function (gameId) {
      var game = App.gameById(gameId);
      var list = byGame[gameId].slice().sort(function (a, b) { return String(b.releasedAt || "").localeCompare(String(a.releasedAt || "")); });
      if (!game || list.length < 2) return;
      var dates = [];
      list.forEach(function (version) {
        var d = App.toDate(version.releasedAt);
        if (d) dates.push(d.getTime());
      });
      if (dates.length < 2) return;
      dates.sort(function (a, b) { return b - a; });
      var intervals = [];
      for (var i = 0; i < dates.length - 1; i++) {
        var days = Math.round((dates[i] - dates[i + 1]) / 86400000);
        if (days > 0) intervals.push(days);
      }
      if (!intervals.length) return;
      var avg = Math.round(intervals.reduce(function (a, b) { return a + b; }, 0) / intervals.length);
      rows.push({ game: game, avg: avg, count: list.length });
    });
    rows.sort(function (a, b) { return a.avg - b.avg; });
    if (!rows.length) return null;
    var box = h("div", { class: "panel" }, [App.comp.sectionTitle("更新节奏", "按已采集版本计算平均间隔")]);
    var grid = h("div", { class: "cadence-grid" });
    rows.slice(0, 10).forEach(function (row) {
      grid.appendChild(h("a", { class: "cadence-card", href: "#/game/" + row.game.id }, [
        h("span", null, row.game.nameZh || row.game.name),
        h("strong", null, "≈" + row.avg + " 天/版"),
        h("small", null, row.count + " 个版本")
      ]));
    });
    box.appendChild(grid);
    return box;
  }

  function render(route) {
    var gameId = route.params.get("game") || "";
    var versions = (App.KB.versions || []).slice().filter(function (version) {
      return !gameId || version.gameId === gameId;
    }).sort(function (a, b) {
      return String(b.releasedAt || "").localeCompare(String(a.releasedAt || "")) || String(b.version || "").localeCompare(String(a.version || ""));
    });
    var week = versions.filter(function (version) {
      var d = App.daysSince(version.releasedAt);
      return d !== null && d >= 0 && d <= 7;
    });
    var fragment = document.createDocumentFragment();
    fragment.appendChild(App.comp.pageHead("版本动态", "App Store 官方版本与更新说明；每天自动追加。这里最适合看“他多久更一次、每次加什么”。"));

    var controls = h("div", { class: "controls" });
    var select = h("select", { class: "control-select", on: { change: function () {
      App.go("versions", "", select.value ? { game: select.value } : {});
    } } });
    select.appendChild(h("option", { value: "" }, "全部游戏"));
    App.sortGames(App.KB.games || []).forEach(function (game) {
      select.appendChild(h("option", { value: game.id, selected: game.id === gameId }, game.nameZh || game.name));
    });
    controls.appendChild(h("label", { class: "control" }, [h("span", null, "游戏"), select]));
    controls.appendChild(h("span", { class: "result-hint" }, "本周更新 " + week.length + " 个版本 · 共 " + versions.length + " 条"));
    fragment.appendChild(controls);

    var cadence = cadenceCards();
    if (cadence && !gameId) fragment.appendChild(cadence);

    if (!versions.length) {
      fragment.appendChild(App.comp.emptyState("还没有版本记录", "运行「更新情报.bat」或等待 GitHub Actions 每日采集。", "看游戏库", function () { App.go("games"); }));
      return fragment;
    }
    var list = h("div", { class: "version-card-list" });
    versions.slice(0, 80).forEach(function (version) { list.appendChild(versionCard(version)); });
    fragment.appendChild(list);
    return fragment;
  }

  App.views.versions = { render: render, title: "版本动态" };
})();
