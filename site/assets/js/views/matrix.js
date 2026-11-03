/* 对标矩阵 */
(function () {
  "use strict";
  var App = (window.App = window.App || {});
  App.views = App.views || {};
  var h = App.h;
  var icon = App.icon;

  var columns = [
    { key: "coreLoop", label: "核心循环" },
    { key: "energy", label: "体力/行动" },
    { key: "events", label: "活动类型" },
    { key: "pass", label: "通行证/订阅" },
    { key: "offers", label: "礼包结构" },
    { key: "ads", label: "广告" },
    { key: "collab", label: "联动" },
    { key: "cadence", label: "更新节奏" },
    { key: "borrow", label: "可借鉴点" }
  ];

  function val(game, key) {
    if (key === "coreLoop") return (game.coreLoop || []).join(" · ");
    if (key === "borrow") return (game.borrow || []).slice(0, 2).join("；");
    return (game.matrix || {})[key] || "待核实";
  }

  function render(route) {
    var role = route.params.get("role") || "all";
    var games = App.sortGames(App.KB.games || []).filter(function (game) {
      return role === "all" ? true : game.role === role;
    });
    var fragment = document.createDocumentFragment();
    fragment.appendChild(App.comp.pageHead("对标矩阵", "把「我们」和竞品放在一张表里：核心循环、体力、活动、通行证、礼包、广告、联动与更新节奏。", [
      h("a", { class: "btn btn-ghost", href: "#/games" }, [icon("games"), "游戏库"])
    ]));

    var tabs = h("div", { class: "tabs" }, [
      ["all", "全部"],
      ["self", "自营"],
      ["competitor", "竞品"]
    ].map(function (pair) {
      return h("button", {
        class: "tab" + (role === pair[0] ? " is-active" : ""),
        type: "button",
        on: { click: function () { App.go("matrix", "", pair[0] === "all" ? {} : { role: pair[0] }); } }
      }, pair[1]);
    }));
    fragment.appendChild(tabs);

    var wrap = h("div", { class: "matrix-wrap" });
    var table = h("table", { class: "matrix-table" });
    var thead = h("thead");
    var headRow = h("tr");
    headRow.appendChild(h("th", { class: "sticky-col" }, "游戏"));
    columns.forEach(function (column) { headRow.appendChild(h("th", null, column.label)); });
    thead.appendChild(headRow);
    table.appendChild(thead);
    var tbody = h("tbody");
    games.forEach(function (game) {
      var row = h("tr", { class: game.role === "self" ? "is-self" : "" });
      var name = h("td", { class: "sticky-col" }, [
        h("a", { class: "matrix-game", href: "#/game/" + game.id }, [
          App.comp.gameAvatar(game, "sm"),
          h("span", null, [h("strong", null, game.nameZh || game.name), h("small", null, game.publisher || "")])
        ])
      ]);
      row.appendChild(name);
      columns.forEach(function (column) {
        var cell = h("td", null, val(game, column.key));
        cell.title = cell.textContent;
        row.appendChild(cell);
      });
      tbody.appendChild(row);
    });
    table.appendChild(tbody);
    wrap.appendChild(table);
    fragment.appendChild(wrap);

    fragment.appendChild(h("p", { class: "matrix-note" }, "「待核实」表示公开资料没有明确说明；不要当成结论。点游戏名进入档案看版本与情报。"));
    return fragment;
  }

  App.views.matrix = { render: render, title: "对标矩阵" };
})();
