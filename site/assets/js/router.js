/* 二合情报站 · 极简 hash 路由 */
(function () {
  "use strict";
  var App = (window.App = window.App || {});
  App.views = App.views || {};

  var TITLES = {
    home: "总览",
    feed: "情报流",
    games: "游戏库",
    game: "游戏档案",
    matrix: "对标矩阵",
    playbook: "拆解库",
    versions: "版本动态",
    radar: "爆款雷达",
    digest: "周报",
    sources: "来源与更新",
    notes: "收藏与笔记",
    settings: "设置"
  };

  function routeView(route) {
    var name = route.name;
    if (App.views[name]) return App.views[name];
    return App.views.home;
  }

  var router = {
    current: null,
    start: function () {
      var self = this;
      if (!window.location.hash) window.location.hash = "#/home";
      window.addEventListener("hashchange", function () { self.render(); });
      self.render();
    },
    go: function (name, id, params) { App.go(name, id, params); },
    refresh: function () {
      try {
        this.render();
      } catch (e) {
        console.error(e);
      }
    },
    render: function () {
      var route = App.parseRoute(window.location.hash);
      App.route = route;
      this.current = route;
      App.comp.closeDrawer();
      var main = document.getElementById("main");
      if (!main) return;
      main.innerHTML = "";
      var view = routeView(route);
      var label = TITLES[route.name] || "二合情报站";
      if (route.name === "game") {
        var game = App.gameById(route.id);
        if (game) label = game.nameZh || game.name;
      }
      if (route.name === "playbook" && route.id) {
        var section = (App.KB.playbook || []).filter(function (item) { return item.id === route.id; })[0];
        if (section) label = section.title;
      }
      document.title = label + " · " + ((App.KB && App.KB.meta && App.KB.meta.siteName) || "二合情报站");
      document.body.dataset.view = route.name;
      try {
        var node = view.render(route);
        if (Array.isArray(node)) {
          var frag = document.createDocumentFragment();
          node.forEach(function (child) { if (child) frag.appendChild(child); });
          main.appendChild(frag);
        } else if (node) {
          main.appendChild(node);
        }
      } catch (error) {
        console.error(error);
        main.appendChild(App.h("div", { class: "empty-state" }, [
          App.icon("alert", "empty-icon"),
          App.h("h3", null, "页面渲染出错"),
          App.h("p", null, String(error && error.message || error)),
          App.h("a", { class: "btn btn-primary", href: "#/home" }, "回到总览")
        ]));
      }
      App.comp.updateNav(route);
      if (route.name !== "game" && route.name !== "playbook") window.scrollTo({ top: 0, behavior: "auto" });
      if (App.store) App.comp.refreshItemStates();
    }
  };

  App.router = router;
})();
