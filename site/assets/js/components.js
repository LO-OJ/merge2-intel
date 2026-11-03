/* 二合情报站 · 通用组件与外壳 */
(function () {
  "use strict";
  var App = (window.App = window.App || {});
  var h = App.h;
  var icon = App.icon;
  var esc = App.escapeHtml;
  var fmt = App.fmt;

  var navGroups = [
    {
      label: "情报",
      items: [
        { name: "home", label: "总览", icon: "home" },
        { name: "feed", label: "情报流", icon: "feed" },
        { name: "radar", label: "爆款雷达", icon: "radar" },
        { name: "digest", label: "周报", icon: "book" }
      ]
    },
    {
      label: "资料库",
      items: [
        { name: "games", label: "游戏库", icon: "games" },
        { name: "matrix", label: "对标矩阵", icon: "grid" },
        { name: "playbook", label: "拆解库", icon: "layers" },
        { name: "versions", label: "版本动态", icon: "tag" }
      ]
    },
    {
      label: "我的",
      items: [
        { name: "notes", label: "收藏与笔记", icon: "bookmark" },
        { name: "sources", label: "来源与更新", icon: "globe" },
        { name: "settings", label: "设置", icon: "settings" }
      ]
    }
  ];
  var bottomItems = [
    { name: "home", label: "总览", icon: "home" },
    { name: "feed", label: "情报", icon: "feed" },
    { name: "games", label: "游戏", icon: "games" },
    { name: "radar", label: "雷达", icon: "radar" }
  ];
  var moreItems = [
    { name: "matrix", label: "对标矩阵", icon: "grid" },
    { name: "playbook", label: "拆解库", icon: "layers" },
    { name: "versions", label: "版本动态", icon: "tag" },
    { name: "digest", label: "周报", icon: "book" },
    { name: "notes", label: "收藏与笔记", icon: "bookmark" },
    { name: "sources", label: "来源与更新", icon: "globe" },
    { name: "settings", label: "设置", icon: "settings" }
  ];

  function el(tag, cls, children) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (children) {
      (Array.isArray(children) ? children : [children]).forEach(function (child) {
        if (child == null) return;
        node.appendChild(child instanceof Node ? child : document.createTextNode(String(child)));
      });
    }
    return node;
  }

  function chip(label, opts) {
    opts = opts || {};
    var node = opts.onClick ? el("button", "chip" + (opts.cls ? " " + opts.cls : "")) : el("span", "chip" + (opts.cls ? " " + opts.cls : ""));
    node.textContent = label;
    if (opts.onClick) {
      node.type = "button";
      node.addEventListener("click", opts.onClick);
    }
    if (opts.active) node.classList.add("is-active");
    if (opts.title) node.title = opts.title;
    return node;
  }

  function badge(text, cls) {
    return el("span", "badge" + (cls ? " " + cls : ""), text);
  }

  function dimChips(dimensions, max) {
    var wrap = el("span", "chip-row");
    (dimensions || []).slice(0, max || 6).forEach(function (dim) {
      wrap.appendChild(chip(App.dimMeta(dim).label, { cls: "chip-dim dim-" + dim }));
    });
    return wrap;
  }

  function confidenceBadge(item) {
    if (!item) return null;
    if (item.confidence === "low") return badge("待核实", "badge-warn");
    if (item.summaryBy === "ai") return badge("AI 提炼", "badge-ai");
    return null;
  }

  function gameAvatar(game, size) {
    var cls = "game-avatar" + (size ? " avatar-" + size : "");
    var node = el("span", cls);
    node.style.setProperty("--game-color", (game && game.color) || "#E4572E");
    node.textContent = (game && (game.logoText || String(game.nameZh || game.name || "?").slice(0, 2))) || "?";
    if (game) node.title = game.nameZh || game.name;
    return node;
  }

  function sourceLink(url, label, cls) {
    if (!url) return null;
    var safe = App.safeUrl(url);
    if (!safe) return null;
    var a = el("a", "source-link" + (cls ? " " + cls : ""), [label || App.host(safe), icon("external", "icon-xs")]);
    a.href = safe;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    return a;
  }

  function pageHead(title, subtitle, actions) {
    return el("header", "page-head", [
      el("div", "page-head-main", [
        el("p", "eyebrow", "MERGE-2 RADAR"),
        el("h1", "page-title", title),
        subtitle ? el("p", "page-sub", subtitle) : null
      ]),
      actions ? el("div", "page-actions", actions) : null
    ]);
  }

  function sectionTitle(title, sub, right) {
    return el("div", "section-title", [
      el("div", null, [el("h2", null, title), sub ? el("p", "section-sub", sub) : null]),
      right || null
    ]);
  }

  function emptyState(title, desc, actionLabel, onAction) {
    var box = el("div", "empty-state", [
      icon("spark", "empty-icon"),
      el("h3", null, title || "暂无内容"),
      el("p", null, desc || "")
    ]);
    if (actionLabel) {
      var btn = el("button", "btn btn-primary", actionLabel);
      btn.type = "button";
      if (onAction) btn.addEventListener("click", onAction);
      box.appendChild(btn);
    }
    return box;
  }

  function stat(label, value, hint) {
    return el("div", "stat", [
      el("span", "stat-label", label),
      el("strong", "stat-value", value == null ? "—" : String(value)),
      hint ? el("span", "stat-hint", hint) : null
    ]);
  }

  function itemMeta(item) {
    var meta = el("div", "item-meta");
    var date = el("span", null, fmt.full(item.publishedAt));
    meta.appendChild(date);
    meta.appendChild(el("span", "dot", "·"));
    meta.appendChild(el("span", null, item.sourceName || item.sourceId || "来源"));
    if (item.importance === 3) meta.appendChild(badge("重点", "badge-important"));
    if (item.importance === 2) meta.appendChild(badge("值得看", "badge-mid"));
    var conf = confidenceBadge(item);
    if (conf) meta.appendChild(conf);
    return meta;
  }

  function itemCard(item, opts) {
    opts = opts || {};
    var gameNames = item.gameNames || [];
    var card = el("article", "item-card importance-" + (item.importance || 1) + (App.store.isRead(item.id) ? " is-read" : ""));
    card.dataset.id = item.id;
    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.setAttribute("aria-label", "打开情报：" + item.title);

    var head = el("div", "item-head", [
      itemMeta(item),
      el("button", "icon-btn item-bookmark" + (App.store.isBookmarked(item.id) ? " is-on" : ""), icon("bookmark"))
    ]);
    head.querySelector("button").type = "button";
    head.querySelector("button").title = "收藏";
    head.querySelector("button").setAttribute("aria-label", "收藏");
    head.querySelector("button").addEventListener("click", function (event) {
      event.stopPropagation();
      var on = App.store.toggleBookmark(item.id);
      this.classList.toggle("is-on", on);
      toast(on ? "已加入收藏" : "已取消收藏");
    });

    var title = el("h3", "item-title", item.title);
    var summary = el("p", "item-summary", item.summary || "");
    var body = el("div", "item-body", [title, summary]);
    if (!opts.compact && item.takeaway) {
      body.appendChild(el("div", "takeaway", [icon("target", "icon-sm"), el("p", null, item.takeaway)]));
    }
    var foot = el("div", "item-foot", [dimChips(item.dimensions, 4)]);
    if (gameNames.length) {
      foot.appendChild(el("span", "item-games", gameNames.slice(0, 3).join(" · ")));
    }
    if (App.store.hasNote(item.id)) foot.appendChild(el("span", "note-flag", [icon("note", "icon-xs"), "有笔记"]));
    var link = sourceLink(item.url, "原文");
    if (link) {
      link.addEventListener("click", function (event) { event.stopPropagation(); });
      foot.appendChild(link);
    }
    card.appendChild(head);
    card.appendChild(body);
    card.appendChild(foot);

    function open(event) {
      if (event && event.target.closest("a,button")) return;
      App.comp.openItem(item);
    }
    card.addEventListener("click", open);
    card.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open(event);
      }
    });
    return card;
  }

  function draftCard(draft) {
    var card = el("article", "item-card draft-card");
    card.appendChild(el("div", "item-head", [
      el("div", "item-meta", [
        el("span", null, fmt.full(draft.publishedAt)),
        el("span", "dot", "·"),
        el("span", null, draft.sourceName || draft.sourceId || "线索"),
        badge("待提炼", "badge-draft")
      ]),
      draft.aiStatus === "enriched" ? badge("AI 已读", "badge-ai") : null
    ]));
    var link = sourceLink(draft.url, draft.title, "draft-title");
    if (link) {
      link.className = "draft-title source-link";
      card.appendChild(link);
    } else {
      card.appendChild(el("h3", "item-title", draft.title));
    }
    if (draft.excerpt) card.appendChild(el("p", "item-summary", draft.excerpt));
    var foot = el("div", "item-foot");
    if (draft.relevance != null) foot.appendChild(badge("相关度 " + Math.round(draft.relevance * 100) + "%", "badge-mid"));
    foot.appendChild(sourceLink(draft.url, "打开原文"));
    card.appendChild(foot);
    return card;
  }

  function series(values, opts) {
    opts = opts || {};
    var width = opts.width || 132;
    var height = opts.height || 34;
    var pad = 3;
    var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 " + width + " " + height);
    svg.setAttribute("class", "sparkline");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", opts.label || "趋势");
    var clean = (values || []).filter(function (v) { return typeof v === "number" && isFinite(v); });
    if (clean.length < 2) {
      var line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", pad); line.setAttribute("x2", width - pad);
      line.setAttribute("y1", height / 2); line.setAttribute("y2", height / 2);
      line.setAttribute("class", "sparkline-flat");
      svg.appendChild(line);
      return svg;
    }
    var min = Math.min.apply(null, clean);
    var max = Math.max.apply(null, clean);
    var span = max - min || 1;
    var step = (width - pad * 2) / (clean.length - 1);
    var points = clean.map(function (value, index) {
      var x = pad + index * step;
      var y = height - pad - ((value - min) / span) * (height - pad * 2);
      return [x, y];
    });
    var poly = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
    poly.setAttribute("points", points.map(function (p) { return p[0].toFixed(1) + "," + p[1].toFixed(1); }).join(" "));
    poly.setAttribute("class", "sparkline-line");
    svg.appendChild(poly);
    var last = points[points.length - 1];
    var dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    dot.setAttribute("cx", last[0]); dot.setAttribute("cy", last[1]); dot.setAttribute("r", 2.4);
    dot.setAttribute("class", "sparkline-dot");
    svg.appendChild(dot);
    return svg;
  }

  var drawerState = { overlay: null, panel: null, lastFocus: null, keydown: null };

  function ensureDrawerRoot() {
    var root = document.getElementById("drawer-root");
    if (!root) {
      root = el("div", "drawer-root");
      root.id = "drawer-root";
      document.body.appendChild(root);
    }
    root.classList.add("drawer-root");
    return root;
  }

  function closeDrawer() {
    if (!drawerState.overlay) return;
    var overlay = drawerState.overlay;
    var lastFocus = drawerState.lastFocus;
    if (drawerState.keydown) document.removeEventListener("keydown", drawerState.keydown, true);
    overlay.classList.remove("is-open");
    document.body.classList.remove("drawer-open");
    setTimeout(function () { if (overlay.parentNode) overlay.parentNode.removeChild(overlay); }, 180);
    drawerState.overlay = null;
    drawerState.panel = null;
    drawerState.keydown = null;
    if (lastFocus && lastFocus.focus) { try { lastFocus.focus(); } catch (e) {} }
  }

  function openDrawer(options) {
    closeDrawer();
    var root = ensureDrawerRoot();
    drawerState.lastFocus = document.activeElement;
    var overlay = el("div", "drawer-overlay");
    var panel = el("aside", "drawer-panel" + (options.wide ? " drawer-wide" : ""));
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-modal", "true");
    panel.setAttribute("aria-label", options.title || "详情");

    var closeBtn = el("button", "icon-btn drawer-close", icon("close"));
    closeBtn.type = "button";
    closeBtn.title = "关闭";
    closeBtn.setAttribute("aria-label", "关闭");
    closeBtn.addEventListener("click", closeDrawer);

    var head = el("div", "drawer-head", [
      el("div", "drawer-heading", [
        options.kicker ? el("p", "eyebrow", options.kicker) : null,
        el("h2", null, options.title || ""),
        options.subtitle ? el("p", "drawer-sub", options.subtitle) : null
      ]),
      closeBtn
    ]);
    var body = el("div", "drawer-body");
    if (options.content) body.appendChild(options.content);
    panel.appendChild(head);
    panel.appendChild(body);
    overlay.appendChild(panel);
    overlay.addEventListener("click", function (event) { if (event.target === overlay) closeDrawer(); });
    root.appendChild(overlay);

    drawerState.overlay = overlay;
    drawerState.panel = panel;
    document.body.classList.add("drawer-open");
    requestAnimationFrame(function () { overlay.classList.add("is-open"); });

    var selector = 'a[href],button:not([disabled]),textarea,input,select,[tabindex]:not([tabindex="-1"])';
    var focusables = panel.querySelectorAll(selector);
    if (focusables.length) focusables[0].focus();

    drawerState.keydown = function (event) {
      if (event.key === "Escape") { closeDrawer(); return; }
      if (event.key !== "Tab") return;
      var items = Array.prototype.filter.call(panel.querySelectorAll(selector), function (node) {
        return node.offsetParent !== null;
      });
      if (!items.length) return;
      var first = items[0];
      var last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", drawerState.keydown, true);
    return closeDrawer;
  }

  function openItem(item) {
    if (!item) return;
    App.store.markRead(item.id);
    refreshItemStates();
    var content = el("div", "item-detail");
    content.appendChild(el("div", "detail-meta", [
      el("span", null, fmt.long(item.publishedAt)),
      el("span", "dot", "·"),
      el("span", null, item.sourceName || item.sourceId || "来源"),
      badge(App.IMPORTANCE[item.importance] || "一般", item.importance === 3 ? "badge-important" : "badge-mid")
    ]));
    content.appendChild(el("p", "detail-summary", item.summary || ""));
    if (item.takeaway) {
      content.appendChild(el("div", "takeaway takeaway-lg", [
        el("div", "takeaway-label", [icon("target", "icon-sm"), "可借鉴动作"]),
        el("p", null, item.takeaway)
      ]));
    }
    var facts = el("div", "fact-grid");
    if (item.gameNames && item.gameNames.length) {
      facts.appendChild(el("div", "fact", [el("span", "fact-label", "涉及游戏"), el("span", null, item.gameNames.join("、"))]));
    }
    if (item.dimensions && item.dimensions.length) {
      facts.appendChild(el("div", "fact", [el("span", "fact-label", "情报维度"), el("span", "chip-row", item.dimensions.map(function (dim) { return chip(App.dimMeta(dim).label, { cls: "chip-dim dim-" + dim }); }))]));
    }
    if (item.tags && item.tags.length) {
      facts.appendChild(el("div", "fact", [el("span", "fact-label", "标签"), el("span", "chip-row", item.tags.map(function (tag) { return chip(tag, { cls: "chip-soft" }); }))]));
    }
    if (item.titleOriginal) {
      facts.appendChild(el("div", "fact", [el("span", "fact-label", "原标题"), el("span", null, item.titleOriginal)]));
    }
    content.appendChild(facts);

    var actions = el("div", "detail-actions");
    var bookmarkBtn = el("button", "btn btn-ghost", [icon("bookmark"), App.store.isBookmarked(item.id) ? "已收藏" : "收藏"]);
    bookmarkBtn.type = "button";
    bookmarkBtn.addEventListener("click", function () {
      var on = App.store.toggleBookmark(item.id);
      bookmarkBtn.lastChild.textContent = on ? "已收藏" : "收藏";
      bookmarkBtn.classList.toggle("is-on", on);
      refreshItemStates();
    });
    actions.appendChild(bookmarkBtn);
    if (item.url) {
      var open = sourceLink(item.url, "打开原文", "btn btn-primary");
      if (open) actions.appendChild(open);
    }
    var copy = el("button", "btn btn-ghost", [icon("copy"), "复制 Markdown"]);
    copy.type = "button";
    copy.addEventListener("click", function () {
      App.copy(App.itemsMarkdown([item])).then(function () { toast("已复制 Markdown"); });
    });
    actions.appendChild(copy);
    content.appendChild(actions);

    var statusRow = el("div", "status-row", [el("span", "fact-label", "我的状态")]);
    [["adopted", "已借鉴"], ["testing", "测试中"], ["ignored", "忽略"]].forEach(function (pair) {
      var btn = el("button", "chip chip-status" + (App.store.getStatus(item.id) === pair[0] ? " is-active" : ""), pair[1]);
      btn.type = "button";
      btn.addEventListener("click", function () {
        App.store.setStatus(item.id, pair[0]);
        Array.prototype.forEach.call(statusRow.querySelectorAll(".chip-status"), function (node) { node.classList.remove("is-active"); });
        if (App.store.getStatus(item.id) === pair[0]) btn.classList.add("is-active");
      });
      statusRow.appendChild(btn);
    });
    content.appendChild(statusRow);

    var noteWrap = el("div", "note-box");
    noteWrap.appendChild(el("div", "note-head", [el("span", "fact-label", "我的笔记"), el("span", "note-hint", "仅保存在本机浏览器")]));
    var textarea = el("textarea", "note-input");
    textarea.rows = 4;
    textarea.placeholder = "记录这条情报和你们产品的关联、待验证点、可落地的改动…";
    textarea.value = App.store.getNote(item.id);
    noteWrap.appendChild(textarea);
    var noteActions = el("div", "note-actions");
    var save = el("button", "btn btn-soft", "保存笔记");
    save.type = "button";
    save.addEventListener("click", function () {
      App.store.setNote(item.id, textarea.value);
      toast("笔记已保存");
      refreshItemStates();
    });
    noteActions.appendChild(save);
    var clear = el("button", "btn btn-ghost", "清空");
    clear.type = "button";
    clear.addEventListener("click", function () {
      textarea.value = "";
      App.store.setNote(item.id, "");
      toast("已清空");
      refreshItemStates();
    });
    noteActions.appendChild(clear);
    noteWrap.appendChild(noteActions);
    content.appendChild(noteWrap);

    var related = (App.KB.items || []).filter(function (other) {
      if (other.id === item.id) return false;
      return (other.gameIds || []).some(function (gameId) { return (item.gameIds || []).indexOf(gameId) >= 0; });
    }).slice(0, 4);
    if (related.length) {
      var rel = el("div", "related");
      rel.appendChild(el("h3", "subhead", "相关情报"));
      related.forEach(function (other) {
        var row = el("button", "related-row");
        row.type = "button";
        row.appendChild(el("span", "related-date", fmt.date(other.publishedAt)));
        row.appendChild(el("span", "related-title", other.title));
        row.appendChild(icon("arrow-right", "icon-xs"));
        row.addEventListener("click", function () { openItem(other); });
        rel.appendChild(row);
      });
      content.appendChild(rel);
    }

    openDrawer({
      title: item.title,
      kicker: item.sourceName || "情报",
      subtitle: fmt.full(item.publishedAt) + " · " + (item.dimensions || []).map(function (d) { return App.dimMeta(d).label; }).join(" / "),
      content: content,
      wide: true
    });
  }

  function refreshItemStates() {
    Array.prototype.forEach.call(document.querySelectorAll(".item-card[data-id]"), function (card) {
      var id = card.dataset.id;
      var item = App.itemById(id);
      if (!item) return;
      card.classList.toggle("is-read", App.store.isRead(id));
      var btn = card.querySelector(".item-bookmark");
      if (btn) btn.classList.toggle("is-on", App.store.isBookmarked(id));
      var noteFlag = card.querySelector(".note-flag");
      if (App.store.hasNote(id) && !noteFlag) {
        var foot = card.querySelector(".item-foot");
        if (foot) foot.appendChild(el("span", "note-flag", [icon("note", "icon-xs"), "有笔记"]));
      } else if (!App.store.hasNote(id) && noteFlag) {
        noteFlag.parentNode.removeChild(noteFlag);
      }
    });
  }

  var toastTimer = null;
  function toast(message) {
    var root = document.getElementById("toast-root");
    if (!root) {
      root = el("div", "toast-root");
      root.id = "toast-root";
      document.body.appendChild(root);
    }
    root.textContent = "";
    var node = el("div", "toast", message);
    root.appendChild(node);
    requestAnimationFrame(function () { node.classList.add("is-on"); });
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      node.classList.remove("is-on");
      setTimeout(function () { if (node.parentNode) node.parentNode.removeChild(node); }, 180);
    }, 2400);
  }

  function applyTheme() {
    var theme = App.store.theme();
    var resolved = theme;
    if (theme === "auto") {
      resolved = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    document.documentElement.setAttribute("data-theme", resolved);
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", resolved === "dark" ? "#121419" : "#f6f1e8");
    var btn = document.getElementById("theme-toggle");
    if (btn) {
      btn.innerHTML = "";
      btn.appendChild(icon(theme === "dark" ? "moon" : theme === "light" ? "sun" : "target"));
      btn.title = "主题：" + (theme === "auto" ? "跟随系统" : theme === "dark" ? "深色" : "浅色") + "（点击切换）";
      btn.setAttribute("aria-label", btn.title);
    }
    document.documentElement.classList.toggle("compact", App.store.compact());
  }

  function renderShell() {
    var meta = App.meta();
    var sidebar = document.getElementById("sidebar");
    if (!sidebar) return;
    sidebar.innerHTML = "";
    var brand = el("a", "brand", [
      el("span", "brand-mark", [el("span"), el("span")]),
      el("span", "brand-copy", [el("strong", null, meta.siteName || "二合情报站"), el("small", null, meta.siteNameEn || "MERGE-2 RADAR")])
    ]);
    brand.href = "#/home";
    sidebar.appendChild(brand);
    sidebar.appendChild(el("div", "side-freshness", [
      el("span", "live-dot"),
      "数据更新 " + (meta.generatedAt ? fmt.full(meta.generatedAt) : "待构建")
    ]));
    navGroups.forEach(function (group) {
      var section = el("div", "side-group");
      section.appendChild(el("p", "side-label", group.label));
      group.items.forEach(function (item) {
        var link = el("a", "side-link");
        link.href = "#/" + item.name;
        link.dataset.nav = item.name;
        link.appendChild(icon(item.icon));
        link.appendChild(el("span", null, item.label));
        var count = navCount(item.name);
        if (count) link.appendChild(el("span", "side-count", count));
        section.appendChild(link);
      });
      sidebar.appendChild(section);
    });
    sidebar.appendChild(el("div", "side-foot", [
      el("span", null, "构建 " + (meta.buildId || "—")),
      el("span", null, "共 " + (meta.itemCount || 0) + " 条情报")
    ]));

    var topbar = document.getElementById("topbar");
    if (topbar) {
      topbar.innerHTML = "";
      var menu = el("button", "icon-btn mobile-only", icon("menu"));
      menu.type = "button";
      menu.id = "mobile-menu";
      menu.setAttribute("aria-label", "打开导航");
      topbar.appendChild(menu);

      var form = el("form", "top-search");
      form.setAttribute("role", "search");
      var input = el("input", "top-search-input");
      input.type = "search";
      input.name = "q";
      input.placeholder = "搜索情报、游戏、标签…";
      input.setAttribute("aria-label", "搜索");
      form.appendChild(icon("search", "top-search-icon"));
      form.appendChild(input);
      form.appendChild(el("kbd", null, "/"));
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        App.go("feed", "", { q: input.value.trim() });
      });
      topbar.appendChild(form);

      var actions = el("div", "top-actions");
      var dataLink = el("a", "top-link", "数据说明");
      dataLink.href = "#/sources";
      actions.appendChild(dataLink);
      var theme = el("button", "icon-btn", icon("target"));
      theme.type = "button";
      theme.id = "theme-toggle";
      theme.addEventListener("click", function () {
        var order = ["auto", "light", "dark"];
        var next = order[(order.indexOf(App.store.theme()) + 1) % order.length];
        App.store.setTheme(next);
        applyTheme();
      });
      actions.appendChild(theme);
      topbar.appendChild(actions);
    }

    var bottom = document.getElementById("bottom-nav");
    if (bottom) {
      bottom.innerHTML = "";
      bottomItems.forEach(function (item) {
        var btn = el("button", "bottom-link");
        btn.type = "button";
        btn.dataset.nav = item.name;
        btn.appendChild(icon(item.icon));
        btn.appendChild(el("span", null, item.label));
        btn.addEventListener("click", function () { App.go(item.name); });
        bottom.appendChild(btn);
      });
      var more = el("button", "bottom-link");
      more.type = "button";
      more.id = "more-toggle";
      more.appendChild(icon("more"));
      more.appendChild(el("span", null, "更多"));
      bottom.appendChild(more);
    }

    var sheet = document.getElementById("more-sheet");
    if (sheet) {
      sheet.innerHTML = "";
      sheet.appendChild(el("div", "sheet-handle"));
      var grid = el("div", "more-grid");
      moreItems.forEach(function (item) {
        var link = el("a", "more-link", [icon(item.icon), el("span", null, item.label)]);
        link.href = "#/" + item.name;
        grid.appendChild(link);
      });
      sheet.appendChild(grid);
    }

    var overlay = document.getElementById("nav-overlay");
    if (overlay) {
      overlay.addEventListener("click", function () {
        sidebar.classList.remove("is-open");
        overlay.classList.remove("is-on");
        if (sheet) sheet.classList.remove("is-on");
      });
    }
    var menuBtn = document.getElementById("mobile-menu");
    if (menuBtn) {
      menuBtn.addEventListener("click", function () {
        sidebar.classList.add("is-open");
        overlay.classList.add("is-on");
      });
    }
    var moreBtn = document.getElementById("more-toggle");
    if (moreBtn) {
      moreBtn.addEventListener("click", function () {
        sheet.classList.toggle("is-on");
        overlay.classList.toggle("is-on");
      });
    }
    document.addEventListener("click", function (event) {
      if (event.target.closest(".side-link,.more-link,.bottom-link")) {
        sidebar.classList.remove("is-open");
        if (overlay) overlay.classList.remove("is-on");
        if (sheet) sheet.classList.remove("is-on");
      }
    });
    applyTheme();
  }

  function navCount(name) {
    if (!App.KB) return "";
    if (name === "feed") return (App.KB.items || []).length;
    if (name === "games") return (App.KB.games || []).length;
    if (name === "radar") return (App.KB.alerts || []).length || "";
    if (name === "notes") {
      var counts = App.store.counts();
      return counts.bookmarks + counts.notes || "";
    }
    return "";
  }

  function updateNav(route) {
    var active = route.name;
    if (active === "game") active = "games";
    if (active === "playbook") active = "playbook";
    if (active === "digest") active = "digest";
    Array.prototype.forEach.call(document.querySelectorAll("[data-nav]"), function (link) {
      var on = link.dataset.nav === active;
      link.classList.toggle("is-active", on);
      if (on) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
    var search = document.querySelector(".top-search-input");
    if (search) {
      if (route.name === "feed") search.value = route.params.get("q") || "";
    }
  }

  function renderList(items, opts) {
    var wrap = el("div", (opts && opts.className) || "item-list");
    (items || []).forEach(function (item) { wrap.appendChild((opts && opts.draft ? draftCard : itemCard)(item, opts)); });
    return wrap;
  }

  var comp = {
    navGroups: navGroups,
    chip: chip,
    badge: badge,
    dimChips: dimChips,
    gameAvatar: gameAvatar,
    sourceLink: sourceLink,
    pageHead: pageHead,
    sectionTitle: sectionTitle,
    emptyState: emptyState,
    stat: stat,
    itemCard: itemCard,
    draftCard: draftCard,
    sparkline: series,
    openDrawer: openDrawer,
    closeDrawer: closeDrawer,
    openItem: openItem,
    toast: toast,
    applyTheme: applyTheme,
    renderShell: renderShell,
    updateNav: updateNav,
    refreshItemStates: refreshItemStates,
    renderList: renderList,
    confidenceBadge: confidenceBadge
  };
  App.comp = comp;
  App.toast = toast;
})();
