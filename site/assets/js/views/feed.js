/* 情报流 */
(function () {
  "use strict";
  var App = (window.App = window.App || {});
  App.views = App.views || {};
  var h = App.h;
  var icon = App.icon;
  var fmt = App.fmt;
  var PAGE = 24;

  function params(route) {
    return {
      q: (route.params.get("q") || "").trim(),
      dim: (route.params.get("dim") || "").split(",").filter(Boolean),
      game: route.params.get("game") || "",
      source: route.params.get("source") || "",
      days: parseInt(route.params.get("days") || "0", 10) || 0,
      importance: parseInt(route.params.get("importance") || "0", 10) || 0,
      kind: route.params.get("kind") || "curated",
      sort: route.params.get("sort") || "new",
      unread: route.params.get("unread") === "1",
      bookmark: route.params.get("bookmark") === "1"
    };
  }

  function applyPatch(current, patch, focusSearch) {
    var next = {};
    ["q", "game", "source", "kind", "sort"].forEach(function (key) {
      var value = patch.hasOwnProperty(key) ? patch[key] : current[key];
      if (value) next[key] = value;
    });
    var dims = patch.hasOwnProperty("dim") ? patch.dim : current.dim;
    if (dims && dims.length) next.dim = dims.join(",");
    ["days", "importance"].forEach(function (key) {
      var value = patch.hasOwnProperty(key) ? patch[key] : current[key];
      if (value) next[key] = value;
    });
    if (patch.hasOwnProperty("unread") ? patch.unread : current.unread) next.unread = 1;
    if (patch.hasOwnProperty("bookmark") ? patch.bookmark : current.bookmark) next.bookmark = 1;
    App._feedFocusSearch = !!focusSearch;
    App.go("feed", "", next);
  }

  function filterItems(items, p) {
    var q = p.q.toLowerCase();
    var minDate = null;
    if (p.days) {
      minDate = new Date();
      minDate.setDate(minDate.getDate() - p.days);
    }
    return items.filter(function (item) {
      if (p.dim.length && !p.dim.some(function (dim) { return (item.dimensions || []).indexOf(dim) >= 0; })) return false;
      if (p.game && (item.gameIds || []).indexOf(p.game) < 0) return false;
      if (p.source && item.sourceId !== p.source) return false;
      if (p.importance && (item.importance || 0) < p.importance) return false;
      if (p.unread && App.store.isRead(item.id)) return false;
      if (p.bookmark && !App.store.isBookmarked(item.id)) return false;
      if (minDate && item.publishedAt) {
        var date = App.toDate(item.publishedAt);
        if (date && date < minDate) return false;
      }
      if (q) {
        var haystack = [
          item.title, item.titleOriginal, item.summary, item.takeaway,
          (item.tags || []).join(" "), (item.gameNames || []).join(" "),
          item.sourceName || "", item.id
        ].join(" ").toLowerCase();
        if (haystack.indexOf(q) < 0) return false;
      }
      return true;
    }).sort(function (a, b) {
      if (p.sort === "importance") {
        var diff = (b.importance || 0) - (a.importance || 0);
        if (diff) return diff;
      }
      return String(b.publishedAt || "").localeCompare(String(a.publishedAt || ""));
    });
  }

  function option(value, label, selected) {
    return h("option", { value: value, selected: selected }, label);
  }

  function select(label, value, options, onChange) {
    var sel = h("select", { class: "control-select", on: { change: function () { onChange(sel.value); } } });
    options.forEach(function (opt) { sel.appendChild(option(opt.value, opt.label, String(opt.value) === String(value))); });
    return h("label", { class: "control" }, [h("span", null, label), sel]);
  }

  function render(route) {
    var p = params(route);
    var allItems = (App.KB.items || []).slice();
    var drafts = (App.KB.drafts || []).slice();
    var isDrafts = p.kind === "drafts" && drafts.length;
    var base = isDrafts ? drafts : allItems;
    var filtered = isDrafts ? base.filter(function (draft) {
      var q = p.q.toLowerCase();
      if (!q) return true;
      return [draft.title, draft.excerpt, draft.sourceName, draft.url].join(" ").toLowerCase().indexOf(q) >= 0;
    }) : filterItems(base, p);
    var fragment = document.createDocumentFragment();
    var counts = App.store.counts();

    var headActions = [
      h("button", { class: "btn btn-ghost", type: "button", on: { click: function () {
        if (!filtered.length) { App.toast("当前筛选没有可导出的情报"); return; }
        App.download("二合情报-" + App.todayISO() + ".md", App.itemsMarkdown(filtered), "text/markdown;charset=utf-8");
      } } }, [icon("download"), "导出 Markdown"]),
      h("button", { class: "btn btn-ghost", type: "button", on: { click: function () {
        if (!filtered.length) return;
        App.store.markAllRead(filtered.map(function (item) { return item.id; }));
        App.toast("已标记 " + filtered.length + " 条为已读");
        App.router.refresh();
      } } }, [icon("check"), "全部已读"])
    ];
    fragment.appendChild(App.comp.pageHead("情报流", "按游戏、维度、来源筛选；点开条目记笔记，收藏与状态只存在本机。", headActions));

    var toolbar = h("div", { class: "toolbar" });
    var searchWrap = h("div", { class: "search-field" }, [icon("search", "icon-sm")]);
    var input = h("input", { type: "search", placeholder: "搜索标题、摘要、标签、游戏…", value: p.q, "aria-label": "搜索情报" });
    var debounced = App.debounce(function () {
      applyPatch(p, { q: input.value.trim() }, true);
    }, 320);
    input.addEventListener("input", debounced);
    searchWrap.appendChild(input);
    toolbar.appendChild(searchWrap);

    var dimBar = h("div", { class: "chip-row dim-filter" });
    dimBar.appendChild(App.comp.chip("全部维度", {
      active: !p.dim.length,
      onClick: function () { applyPatch(p, { dim: [] }); }
    }));
    App.DIMS.forEach(function (dim) {
      dimBar.appendChild(App.comp.chip(dim.label, {
        cls: "chip-dim dim-" + dim.id,
        active: p.dim.indexOf(dim.id) >= 0,
        onClick: function () {
          var next = p.dim.slice();
          var index = next.indexOf(dim.id);
          if (index >= 0) next.splice(index, 1);
          else next.push(dim.id);
          applyPatch(p, { dim: next });
        }
      }));
    });
    toolbar.appendChild(dimBar);

    var controls = h("div", { class: "controls" });
    var gameOpts = [{ value: "", label: "全部游戏" }].concat(App.sortGames(App.KB.games || []).map(function (game) {
      return { value: game.id, label: game.nameZh || game.name };
    }));
    controls.appendChild(select("游戏", p.game, gameOpts, function (value) { applyPatch(p, { game: value }); }));

    var sourceOpts = [{ value: "", label: "全部来源" }].concat((App.KB.sources || []).filter(function (source) {
      return (source.itemCount || 0) > 0;
    }).map(function (source) { return { value: source.id, label: source.name }; }));
    controls.appendChild(select("来源", p.source, sourceOpts, function (value) { applyPatch(p, { source: value }); }));

    controls.appendChild(select("时间", p.days, [
      { value: 0, label: "全部时间" }, { value: 7, label: "近 7 天" },
      { value: 30, label: "近 30 天" }, { value: 90, label: "近 90 天" },
      { value: 365, label: "近一年" }
    ], function (value) { applyPatch(p, { days: parseInt(value, 10) }); }));

    controls.appendChild(select("重要度", p.importance, [
      { value: 0, label: "全部" }, { value: 2, label: "值得看以上" }, { value: 3, label: "仅重点" }
    ], function (value) { applyPatch(p, { importance: parseInt(value, 10) }); }));

    controls.appendChild(select("排序", p.sort, [
      { value: "new", label: "按日期" }, { value: "importance", label: "按重要度" }
    ], function (value) { applyPatch(p, { sort: value }); }));

    var toggles = h("div", { class: "toggle-row" });
    toggles.appendChild(h("button", { class: "chip" + (p.unread ? " is-active" : ""), type: "button", on: { click: function () { applyPatch(p, { unread: !p.unread }); } } }, "仅未读"));
    toggles.appendChild(h("button", { class: "chip" + (p.bookmark ? " is-active" : ""), type: "button", on: { click: function () { applyPatch(p, { bookmark: !p.bookmark }); } } }, "仅收藏"));
    if (p.q || p.dim.length || p.game || p.source || p.days || p.importance || p.unread || p.bookmark) {
      toggles.appendChild(h("button", { class: "text-link", type: "button", on: { click: function () { App.go("feed"); } } }, "清除筛选"));
    }
    controls.appendChild(toggles);
    toolbar.appendChild(controls);
    fragment.appendChild(toolbar);

    var tabs = h("div", { class: "tabs" }, [
      h("button", { class: "tab" + (!isDrafts ? " is-active" : ""), type: "button", on: { click: function () { applyPatch(p, { kind: "curated" }); } } }, ["正式情报 ", h("span", { class: "tab-count" }, allItems.length)]),
      h("button", { class: "tab" + (isDrafts ? " is-active" : ""), type: "button", on: { click: function () { applyPatch(p, { kind: "drafts" }); } } }, ["线索 ", h("span", { class: "tab-count" }, drafts.length), drafts.length ? null : h("span", { class: "tab-hint" }, "待提炼")])
    ]);
    fragment.appendChild(tabs);

    var resultLine = h("div", { class: "result-line" }, [
      h("span", null, "共 " + filtered.length + " 条" + (isDrafts ? "线索" : "情报")),
      p.q ? h("span", { class: "result-query" }, "关键词：" + p.q) : null,
      h("span", { class: "result-hint" }, "已读 " + counts.read + " · 收藏 " + counts.bookmarks + " · 笔记 " + counts.notes)
    ]);
    fragment.appendChild(resultLine);

    if (!filtered.length) {
      fragment.appendChild(App.comp.emptyState(
        isDrafts ? "暂无待提炼线索" : "没有匹配的情报",
        isDrafts ? "采集脚本抓到的新线索会先出现在这里；配置 DeepSeek key 后可自动提炼。" : "试试减少筛选条件，或换一个维度/游戏。",
        "清除筛选",
        function () { App.go("feed"); }
      ));
    } else {
      var list = h("div", { class: "item-list" });
      var rendered = 0;
      function appendPage() {
        var slice = filtered.slice(rendered, rendered + PAGE);
        slice.forEach(function (item) {
          list.appendChild(isDrafts ? App.comp.draftCard(item) : App.comp.itemCard(item));
        });
        rendered += slice.length;
        if (rendered >= filtered.length && more) more.remove();
        if (more) more.textContent = "加载更多（还有 " + (filtered.length - rendered) + " 条）";
      }
      var more = null;
      fragment.appendChild(list);
      appendPage();
      if (rendered < filtered.length) {
        more = h("button", { class: "btn btn-ghost load-more", type: "button" }, "加载更多（还有 " + (filtered.length - rendered) + " 条）");
        more.addEventListener("click", appendPage);
        fragment.appendChild(more);
      }
    }

    if (App._feedFocusSearch) {
      App._feedFocusSearch = false;
      setTimeout(function () {
        input.focus();
        try { input.setSelectionRange(input.value.length, input.value.length); } catch (e) {}
      }, 0);
    }
    return fragment;
  }

  App.views.feed = { render: render, title: "情报流" };
})();
