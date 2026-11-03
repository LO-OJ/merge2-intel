/* 二合情报站 · 基础工具（无依赖，file:// 可用） */
(function () {
  "use strict";
  var App = (window.App = window.App || {});

  App.DIMS = [
    { id: "activity", label: "活动运营", short: "活动" },
    { id: "system", label: "系统设计", short: "系统" },
    { id: "launch", label: "新活动/上新", short: "上新" },
    { id: "monetization", label: "商业模式", short: "商业" },
    { id: "economy", label: "数值/经济", short: "数值" },
    { id: "market", label: "市场/榜单", short: "市场" },
    { id: "ua", label: "买量/素材", short: "买量" },
    { id: "publisher", label: "厂商动态", short: "厂商" },
    { id: "version", label: "版本更新", short: "版本" }
  ];
  App.DIM_MAP = {};
  App.DIMS.forEach(function (d) { App.DIM_MAP[d.id] = d; });

  App.ROLES = {
    self: { label: "自营", cls: "role-self" },
    competitor: { label: "竞品", cls: "role-competitor" },
    watch: { label: "观察", cls: "role-watch" }
  };
  App.ROLE_ORDER = { self: 0, competitor: 1, watch: 2 };
  App.IMPORTANCE = { 1: "一般", 2: "值得看", 3: "重点" };
  App.CONFIDENCE = { high: "高", medium: "中", low: "低" };
  App.STATUS = { adopted: "已借鉴", testing: "测试中", ignored: "忽略" };

  function append(el, children) {
    for (var i = 0; i < children.length; i++) {
      var child = children[i];
      if (child === null || child === undefined || child === false) continue;
      if (Array.isArray(child)) {
        append(el, child);
      } else if (child instanceof Node) {
        el.appendChild(child);
      } else {
        el.appendChild(document.createTextNode(String(child)));
      }
    }
  }

  App.h = function (tag, attrs) {
    var el = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (key) {
        var value = attrs[key];
        if (value === null || value === undefined || value === false) return;
        if (key === "class" || key === "className") {
          el.className = value;
        } else if (key === "dataset") {
          Object.keys(value).forEach(function (k) { el.dataset[k] = value[k]; });
        } else if (key === "style" && typeof value === "object") {
          Object.keys(value).forEach(function (k) { el.style[k] = value[k]; });
        } else if (key === "on" && typeof value === "object") {
          Object.keys(value).forEach(function (evt) { el.addEventListener(evt, value[evt]); });
        } else if (key === "html") {
          el.innerHTML = value;
        } else if (key === "text") {
          el.textContent = value;
        } else if (key.indexOf("aria-") === 0 || key === "role" || key === "tabindex" || key.indexOf("data-") === 0) {
          el.setAttribute(key, value === true ? "true" : value);
        } else if (key in el && key !== "list" && key !== "form" && key !== "type") {
          try { el[key] = value; } catch (e) { el.setAttribute(key, value); }
        } else {
          el.setAttribute(key, value);
        }
      });
    }
    append(el, Array.prototype.slice.call(arguments, 2));
    return el;
  };

  App.text = function (tag, value, cls) {
    return App.h(tag || "span", cls ? { class: cls } : null, value == null ? "" : value);
  };

  App.frag = function () {
    var frag = document.createDocumentFragment();
    append(frag, Array.prototype.slice.call(arguments));
    return frag;
  };

  App.icon = function (name, cls) {
    var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "1.8");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    svg.setAttribute("class", "icon" + (cls ? " " + cls : ""));
    svg.innerHTML = (App.ICONS || {})[name] || (App.ICONS || {}).info || "";
    return svg;
  };

  App.escapeHtml = function (value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  };

  App.safeUrl = function (url) {
    try {
      var u = new URL(url);
      return u.protocol === "http:" || u.protocol === "https:" ? u.href : "";
    } catch (e) {
      return "";
    }
  };

  App.host = function (url) {
    try { return new URL(url).hostname.replace(/^www\./, ""); } catch (e) { return ""; }
  };

  App.parseRoute = function (hash) {
    var raw = String(hash || "").replace(/^#\/?/, "");
    var qIndex = raw.indexOf("?");
    var pathPart = qIndex >= 0 ? raw.slice(0, qIndex) : raw;
    var queryPart = qIndex >= 0 ? raw.slice(qIndex + 1) : "";
    var segs = pathPart.split("/").filter(Boolean);
    var params = new URLSearchParams(queryPart);
    return { name: segs[0] || "home", id: segs[1] || "", params: params, raw: raw };
  };

  App.hashFor = function (name, id, params) {
    var path = "#/" + name + (id ? "/" + id : "");
    var query = "";
    if (params) {
      var usp = new URLSearchParams();
      Object.keys(params).forEach(function (key) {
        var value = params[key];
        if (value === null || value === undefined || value === "" || value === false) return;
        if (Array.isArray(value)) {
          if (!value.length) return;
          usp.set(key, value.join(","));
        } else if (value === true) {
          usp.set(key, "1");
        } else {
          usp.set(key, String(value));
        }
      });
      query = usp.toString();
    }
    return path + (query ? "?" + query : "");
  };

  App.go = function (name, id, params) {
    window.location.hash = App.hashFor(name, id, params);
  };

  App.todayISO = function () {
    var d = new Date();
    var pad = function (n) { return n < 10 ? "0" + n : "" + n; };
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
  };

  App.toDate = function (iso) {
    if (!iso) return null;
    var d = new Date(iso + (String(iso).length === 10 ? "T00:00:00+08:00" : ""));
    return isNaN(d.getTime()) ? null : d;
  };

  App.daysSince = function (iso) {
    var d = App.toDate(iso);
    if (!d) return null;
    var today = App.toDate(App.todayISO());
    return Math.round((today - d) / 86400000);
  };

  App.fmt = {
    date: function (iso) {
      if (!iso) return "—";
      var s = String(iso);
      return s.length >= 10 ? s.slice(5, 10) : s;
    },
    full: function (iso) {
      if (!iso) return "—";
      var s = String(iso);
      return s.length >= 10 ? s.slice(0, 10) : s;
    },
    long: function (iso) {
      var d = App.toDate(iso);
      if (!d) return iso || "—";
      var week = "日一二三四五六".charAt(d.getDay());
      return d.getFullYear() + "年" + (d.getMonth() + 1) + "月" + d.getDate() + "日 周" + week;
    },
    rel: function (iso) {
      var days = App.daysSince(iso);
      if (days === null) return "";
      if (days < 0) return "未来";
      if (days === 0) return "今天";
      if (days === 1) return "昨天";
      if (days < 7) return days + " 天前";
      if (days < 30) return Math.floor(days / 7) + " 周前";
      if (days < 365) return Math.floor(days / 30) + " 个月前";
      return Math.floor(days / 365) + " 年前";
    },
    num: function (value) {
      if (value === null || value === undefined || isNaN(value)) return "—";
      return new Intl.NumberFormat("zh-CN").format(Number(value));
    },
    compact: function (value) {
      var n = Number(value);
      if (!isFinite(n)) return "—";
      if (n >= 100000000) return (n / 100000000).toFixed(1).replace(/\.0$/, "") + "亿";
      if (n >= 10000) return (n / 10000).toFixed(1).replace(/\.0$/, "") + "万";
      return String(n);
    },
    dash: function (value) { return value === null || value === undefined || value === "" ? "—" : value; }
  };

  App.dimMeta = function (id) {
    return App.DIM_MAP[id] || { id: id, label: id, short: id };
  };

  App.sourceName = function (id) {
    var sources = (App.KB && App.KB.sources) || [];
    for (var i = 0; i < sources.length; i++) {
      if (sources[i].id === id) return sources[i].name;
    }
    return id || "来源";
  };

  App.gameById = function (id) {
    var games = (App.KB && App.KB.games) || [];
    for (var i = 0; i < games.length; i++) if (games[i].id === id) return games[i];
    return null;
  };

  App.itemById = function (id) {
    var items = (App.KB && App.KB.items) || [];
    for (var i = 0; i < items.length; i++) if (items[i].id === id) return items[i];
    return null;
  };

  App.latestVersion = function (game) {
    if (!game) return null;
    var stores = game.latestVersion || {};
    var order = ["cn", "us", "jp", "kr"];
    for (var i = 0; i < order.length; i++) if (stores[order[i]]) return stores[order[i]];
    var keys = Object.keys(stores);
    return keys.length ? stores[keys[0]] : null;
  };

  App.sortGames = function (games) {
    return games.slice().sort(function (a, b) {
      var ra = App.ROLE_ORDER[a.role] == null ? 9 : App.ROLE_ORDER[a.role];
      var rb = App.ROLE_ORDER[b.role] == null ? 9 : App.ROLE_ORDER[b.role];
      if (ra !== rb) return ra - rb;
      return String(a.nameZh || a.name).localeCompare(String(b.nameZh || b.name), "zh-CN");
    });
  };

  App.storeLabel = function (store) {
    return { cn: "中国区", us: "美区", jp: "日区", kr: "韩区", hk: "港区", tw: "台区" }[store] || store;
  };

  App.countryLabel = function (country) {
    return { us: "美国", cn: "中国", jp: "日本", kr: "韩国", hk: "香港", tw: "台湾" }[country] || country;
  };

  App.alertLabel = function (type) {
    return {
      top5: "进入前 5",
      "new-entry": "新面孔",
      "rank-jump": "排名跃升",
      version: "版本更新",
      "suspect-hit": "疑似爆款"
    }[type] || type;
  };

  App.debounce = function (fn, wait) {
    var timer = null;
    return function () {
      var args = arguments;
      var self = this;
      clearTimeout(timer);
      timer = setTimeout(function () { fn.apply(self, args); }, wait);
    };
  };

  App.uniq = function (list) {
    var seen = {};
    return (list || []).filter(function (item) {
      if (seen[item]) return false;
      seen[item] = true;
      return true;
    });
  };

  App.copy = function (text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      try {
        var ta = document.createElement("textarea");
        ta.value = text;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
        resolve();
      } catch (e) { reject(e); }
    });
  };

  App.download = function (filename, content, mime) {
    var blob = new Blob([content], { type: mime || "text/plain;charset=utf-8" });
    var url = URL.createObjectURL(blob);
    var a = App.h("a", { href: url, download: filename });
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 2000);
  };

  App.itemsMarkdown = function (items) {
    var lines = [];
    lines.push("# 二合情报站 · 情报导出");
    lines.push("");
    lines.push("> 导出时间：" + new Date().toLocaleString("zh-CN"));
    lines.push("");
    items.forEach(function (item) {
      lines.push("## " + item.title);
      lines.push("");
      var meta = [
        "日期：" + (item.publishedAt || "—"),
        "来源：" + (item.sourceName || item.sourceId || "—"),
        "维度：" + (item.dimensions || []).map(function (d) { return App.dimMeta(d).label; }).join("、"),
        "重要度：" + (App.IMPORTANCE[item.importance] || item.importance)
      ];
      lines.push("- " + meta.join(" · "));
      if (item.gameNames && item.gameNames.length) lines.push("- 游戏：" + item.gameNames.join("、"));
      lines.push("");
      lines.push(item.summary || "");
      lines.push("");
      if (item.takeaway) {
        lines.push("**可借鉴动作：** " + item.takeaway);
        lines.push("");
      }
      if (item.url) lines.push("[原文](" + item.url + ")");
      lines.push("");
      lines.push("---");
      lines.push("");
    });
    return lines.join("\n");
  };

  App.meta = function () {
    return (App.KB && App.KB.meta) || {};
  };
})();
