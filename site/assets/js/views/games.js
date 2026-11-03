/* 游戏库 */
(function () {
  "use strict";
  var App = (window.App = window.App || {});
  App.views = App.views || {};
  var h = App.h;
  var icon = App.icon;
  var fmt = App.fmt;

  function gameCard(game) {
    var version = App.latestVersion(game);
    var search = [
      game.name, game.nameZh, game.publisher, game.genre, game.positioning,
      (game.tags || []).join(" "), (game.selfFocus || []).join(" ")
    ].join(" ").toLowerCase();
    var card = h("a", { class: "game-card game-card-lg", href: "#/game/" + game.id, "data-search": search }, [
      h("div", { class: "game-card-head" }, [
        App.comp.gameAvatar(game, "lg"),
        h("div", { class: "game-card-title" }, [
          h("strong", null, game.nameZh || game.name),
          h("span", null, game.name + (game.publisher ? " · " + game.publisher : ""))
        ]),
        h("span", { class: "badge " + (App.ROLES[game.role] || {}).cls }, (App.ROLES[game.role] || {}).label || game.role)
      ]),
      h("p", { class: "game-genre" }, game.genre || "品类待补充"),
      h("p", { class: "game-position" }, game.positioning || "档案整理中，先看关联情报与版本动态。"),
      h("div", { class: "game-card-meta" }, [
        h("span", null, [icon("tag", "icon-xs"), version ? "v" + version.version : "版本待采集"]),
        h("span", null, [icon("feed", "icon-xs"), (game.itemCount || 0) + " 条情报"]),
        h("span", null, [icon("clock", "icon-xs"), version && version.releasedAt ? fmt.rel(version.releasedAt) : "—"])
      ]),
      (game.tags && game.tags.length) ? h("div", { class: "chip-row" }, game.tags.slice(0, 4).map(function (tag) {
        return App.comp.chip(tag, { cls: "chip-soft chip-xs" });
      })) : null
    ]);
    return card;
  }

  function render(route) {
    var role = route.params.get("role") || "all";
    var games = App.sortGames(App.KB.games || []);
    var filtered = role === "all" ? games : games.filter(function (game) { return game.role === role; });
    var fragment = document.createDocumentFragment();
    fragment.appendChild(App.comp.pageHead("游戏库", "6 款自营 + 10 款竞品；版本、榜单、活动与可借鉴点都在档案里。", [
      h("a", { class: "btn btn-ghost", href: "#/matrix" }, [icon("grid"), "对标矩阵"])
    ]));

    var tabs = h("div", { class: "tabs" }, [
      ["all", "全部 " + games.length],
      ["self", "自营 " + games.filter(function (g) { return g.role === "self"; }).length],
      ["competitor", "竞品 " + games.filter(function (g) { return g.role === "competitor"; }).length]
    ].map(function (pair) {
      return h("button", {
        class: "tab" + (role === pair[0] ? " is-active" : ""),
        type: "button",
        on: { click: function () { App.go("games", "", pair[0] === "all" ? {} : { role: pair[0] }); } }
      }, pair[1]);
    }));
    fragment.appendChild(tabs);

    var search = h("div", { class: "search-field games-search" }, [icon("search", "icon-sm")]);
    var input = h("input", { type: "search", placeholder: "搜索游戏、厂商、品类…", "aria-label": "搜索游戏" });
    search.appendChild(input);
    fragment.appendChild(search);

    var grid = h("div", { class: "game-grid game-grid-wide" }, filtered.map(func));
    function func(game) { return gameCard(game); }
    fragment.appendChild(grid);

    var empty = App.comp.emptyState("没有匹配的游戏", "换个角色或关键词试试。", "清除", function () { App.go("games"); });
    empty.hidden = true;
    fragment.appendChild(empty);

    input.addEventListener("input", function () {
      var q = input.value.trim().toLowerCase();
      var visible = 0;
      Array.prototype.forEach.call(grid.children, function (card) {
        var show = !q || (card.dataset.search || "").indexOf(q) >= 0;
        card.hidden = !show;
        if (show) visible += 1;
      });
      empty.hidden = visible > 0;
      grid.hidden = visible === 0;
    });
    return fragment;
  }

  App.views.games = { render: render, title: "游戏库" };
})();
