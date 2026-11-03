/* 收藏与笔记 */
(function () {
  "use strict";
  var App = (window.App = window.App || {});
  App.views = App.views || {};
  var h = App.h;
  var icon = App.icon;
  var fmt = App.fmt;

  function noteEntry(item) {
    return h("div", { class: "note-entry" }, [
      App.comp.itemCard(item, { compact: true }),
      h("div", { class: "note-preview" }, [icon("note", "icon-xs"), h("p", null, App.store.getNote(item.id))])
    ]);
  }

  function gameNotes() {
    var snapshot = App.store.snapshot();
    var notes = snapshot.notes || {};
    var rows = [];
    Object.keys(notes).forEach(function (key) {
      if (key.indexOf("game:") !== 0) return;
      var game = App.gameById(key.slice(5));
      if (!game) return;
      var text = String(notes[key] || "").trim();
      if (!text) return;
      rows.push({ game: game, text: text });
    });
    return rows;
  }

  function render(route) {
    var tab = route.params.get("tab") || "bookmark";
    var counts = App.store.counts();
    var gameNoteRows = gameNotes();
    var fragment = document.createDocumentFragment();
    fragment.appendChild(App.comp.pageHead("收藏与笔记", "个人记录只保存在本机浏览器；导出 JSON 可迁移到其他设备。"));
    fragment.appendChild(h("div", { class: "stat-grid" }, [
      App.comp.stat("收藏", counts.bookmarks, "条"),
      App.comp.stat("笔记", counts.notes, "条情报"),
      App.comp.stat("行动勾选", counts.checklist, "项"),
      App.comp.stat("游戏备注", gameNoteRows.length, "款")
    ]));

    var tabs = h("div", { class: "tabs" }, [
      ["bookmark", "收藏", counts.bookmarks],
      ["notes", "情报笔记", counts.notes],
      ["adopted", "已借鉴", App.store.statusIds("adopted").length],
      ["testing", "测试中", App.store.statusIds("testing").length],
      ["game", "游戏备注", gameNoteRows.length]
    ].map(function (item) {
      return h("button", {
        class: "tab" + (tab === item[0] ? " is-active" : ""),
        type: "button",
        on: { click: function () { App.go("notes", "", item[0] === "bookmark" ? {} : { tab: item[0] }); } }
      }, [item[1] + " ", h("span", { class: "tab-count" }, item[2])]);
    }));
    fragment.appendChild(tabs);

    var content = h("div", { class: "notes-content" });
    if (tab === "game") {
      if (!gameNoteRows.length) {
        content.appendChild(App.comp.emptyState("还没有游戏备注", "在游戏档案页写下备注后，会汇总到这里。", "去游戏库", function () { App.go("games"); }));
      } else {
        gameNoteRows.forEach(function (row) {
          content.appendChild(h("a", { class: "game-note-row", href: "#/game/" + row.game.id }, [
            App.comp.gameAvatar(row.game, "sm"),
            h("div", null, [h("strong", null, row.game.nameZh || row.game.name), h("p", null, row.text)]),
            icon("arrow-right", "icon-xs")
          ]));
        });
      }
    } else {
      var ids = tab === "bookmark" ? App.store.bookmarkedIds() :
        tab === "notes" ? App.store.notedIds() :
          App.store.statusIds(tab);
      var items = ids.map(App.itemById).filter(Boolean).sort(function (a, b) {
        return String(b.publishedAt || "").localeCompare(String(a.publishedAt || ""));
      });
      if (!items.length) {
        content.appendChild(App.comp.emptyState("这里还是空的", "在情报流里收藏、写笔记或标记状态后，会出现在这里。", "去情报流", function () { App.go("feed"); }));
      } else {
        var list = h("div", { class: "item-list" });
        items.forEach(function (item) {
          if (tab === "notes") list.appendChild(noteEntry(item));
          else list.appendChild(App.comp.itemCard(item, { compact: true }));
        });
        content.appendChild(list);
      }
    }
    fragment.appendChild(content);

    var transfer = h("div", { class: "panel" }, [
      App.comp.sectionTitle("迁移与清理", "换设备或备份时使用"),
      h("div", { class: "button-row" }, [
        h("button", { class: "btn btn-soft", type: "button", on: { click: function () {
          App.download("二合情报-我的记录-" + App.todayISO() + ".json", App.store.exportJSON(), "application/json;charset=utf-8");
        } } }, [icon("download"), "导出个人数据"]),
        (function () {
          var input = h("input", { type: "file", accept: ".json,application/json", class: "file-input" });
          input.addEventListener("change", function () {
            var file = input.files && input.files[0];
            if (!file) return;
            var reader = new FileReader();
            reader.onload = function () {
              try {
                var result = App.store.importJSON(String(reader.result || ""));
                App.toast("已导入：收藏 " + result.bookmarks + " · 笔记 " + result.notes);
                App.router.refresh();
              } catch (error) {
                App.toast("导入失败：" + error.message);
              }
            };
            reader.readAsText(file, "utf-8");
          });
          var label = h("label", { class: "btn btn-ghost file-btn" }, [icon("upload"), "导入个人数据", input]);
          return label;
        })(),
        h("button", { class: "btn btn-danger", type: "button", on: { click: function () {
          if (!window.confirm("确定清空本机的收藏、笔记、已读与行动勾选吗？建议先导出备份。")) return;
          App.store.clearPersonal();
          App.toast("已清空个人记录");
          App.router.refresh();
        } } }, [icon("trash"), "清空个人记录"])
      ]),
      h("p", { class: "muted small" }, "个人数据保存在浏览器 localStorage，不会上传、不会进入公开站点；清理浏览器数据会一并清空。")
    ]);
    fragment.appendChild(transfer);
    return fragment;
  }

  App.views.notes = { render: render, title: "收藏与笔记" };
})();
