/* 拆解库 */
(function () {
  "use strict";
  var App = (window.App = window.App || {});
  App.views = App.views || {};
  var h = App.h;
  var icon = App.icon;

  function sectionCard(section) {
    return h("a", { class: "playbook-card", href: "#/playbook/" + section.id }, [
      h("div", { class: "playbook-card-top" }, [
        h("span", { class: "dim-dot dim-" + section.dimension }),
        h("span", { class: "badge badge-soft" }, App.dimMeta(section.dimension).label),
        h("span", { class: "playbook-count" }, (section.principles || []).length + " 条原则 · " + (section.checklist || []).length + " 个动作")
      ]),
      h("h2", null, section.title),
      h("p", null, section.summary || ""),
      h("div", { class: "playbook-card-foot" }, [
        h("span", null, "打开章节 "),
        icon("arrow-right", "icon-xs")
      ])
    ]);
  }

  function renderDetail(section) {
    var fragment = document.createDocumentFragment();
    fragment.appendChild(h("a", { class: "back-link", href: "#/playbook" }, [icon("arrow-left", "icon-xs"), "拆解库"]));
    fragment.appendChild(h("header", { class: "playbook-hero" }, [
      h("div", { class: "chip-row" }, [
        h("span", { class: "badge badge-soft" }, App.dimMeta(section.dimension).label),
        h("span", { class: "muted" }, (section.principles || []).length + " 条原则")
      ]),
      h("h1", null, section.title),
      h("p", null, section.summary || "")
    ]));

    var principles = h("div", { class: "panel" }, [App.comp.sectionTitle("原则", "从案例里抽出来的可复用判断")]);
    (section.principles || []).forEach(function (principle, index) {
      var evidence = (principle.evidence || []).map(function (id) { return App.itemById(id); }).filter(Boolean);
      principles.appendChild(h("div", { class: "principle" }, [
        h("span", { class: "principle-index" }, String(index + 1).padStart(2, "0")),
        h("div", null, [
          h("h3", null, principle.title),
          h("p", null, principle.detail),
          evidence.length ? h("div", { class: "evidence-row" }, evidence.map(function (item) {
            var btn = h("button", { class: "evidence-chip", type: "button", title: item.title }, [icon("link", "icon-xs"), item.title.slice(0, 26) + (item.title.length > 26 ? "…" : "")]);
            btn.addEventListener("click", function () { App.comp.openItem(item); });
            return btn;
          })) : null
        ])
      ]));
    });
    fragment.appendChild(principles);

    if (section.cases && section.cases.length) {
      var cases = h("div", { class: "panel" }, [App.comp.sectionTitle("案例")]);
      section.cases.forEach(function (item) {
        var game = App.gameById(item.gameId);
        cases.appendChild(h("div", { class: "case" }, [
          h("div", { class: "case-head" }, [
            game ? h("a", { class: "case-game", href: "#/game/" + game.id }, [App.comp.gameAvatar(game, "sm"), game.nameZh || game.name]) : h("span", null, item.gameId || "案例"),
            item.sourceUrl ? App.comp.sourceLink(item.sourceUrl, "来源") : null
          ]),
          h("p", null, item.detail || "")
        ]));
      });
      fragment.appendChild(cases);
    }

    var checklist = h("div", { class: "panel" }, [App.comp.sectionTitle("行动清单", "勾选会保存在本机")]);
    (section.checklist || []).forEach(function (text, index) {
      var key = "pb-" + section.id + "-" + index;
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
    fragment.appendChild(checklist);
    return fragment;
  }

  function render(route) {
    var sections = (App.KB.playbook || []).slice().sort(function (a, b) {
      return (a.title || "").localeCompare(b.title || "", "zh-CN");
    });
    if (route.id) {
      var section = sections.filter(function (item) { return item.id === route.id; })[0];
      if (!section) return App.comp.emptyState("找不到这个章节", "链接可能有误。", "回到拆解库", function () { App.go("playbook"); });
      return renderDetail(section);
    }
    var fragment = document.createDocumentFragment();
    fragment.appendChild(App.comp.pageHead("拆解库", "活动节奏、限时活动、Merge 核心、元游戏、经济数值、变现、新手与买量——每章都带案例和行动清单。"));
    if (!sections.length) {
      fragment.appendChild(App.comp.emptyState("还没有拆解章节", "内容整理完成后会出现在这里。", "看情报流", function () { App.go("feed"); }));
      return fragment;
    }
    var grid = h("div", { class: "playbook-grid" });
    sections.forEach(function (section) { grid.appendChild(sectionCard(section)); });
    fragment.appendChild(grid);
    return fragment;
  }

  App.views.playbook = { render: render, title: "拆解库" };
})();
