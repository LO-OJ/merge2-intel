/* 二合情报站 · 本地个人状态（收藏/笔记/已读/行动清单） */
(function () {
  "use strict";
  var App = (window.App = window.App || {});
  var KEY = "merge2.personal.v1";
  var DEFAULTS = {
    v: 1,
    read: {},
    bookmark: {},
    status: {},
    notes: {},
    checklist: {},
    theme: "auto",
    compact: false
  };

  function load() {
    try {
      var raw = window.localStorage.getItem(KEY);
      if (!raw) return JSON.parse(JSON.stringify(DEFAULTS));
      var parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== "object") return JSON.parse(JSON.stringify(DEFAULTS));
      var merged = JSON.parse(JSON.stringify(DEFAULTS));
      Object.keys(merged).forEach(function (key) {
        if (parsed[key] !== undefined && parsed[key] !== null) merged[key] = parsed[key];
      });
      ["read", "bookmark", "status", "notes", "checklist"].forEach(function (key) {
        if (typeof merged[key] !== "object" || Array.isArray(merged[key])) merged[key] = {};
      });
      if (["auto", "light", "dark"].indexOf(merged.theme) < 0) merged.theme = "auto";
      return merged;
    } catch (e) {
      return JSON.parse(JSON.stringify(DEFAULTS));
    }
  }

  var data = load();
  var bus = new EventTarget();

  function persist() {
    try {
      window.localStorage.setItem(KEY, JSON.stringify(data));
    } catch (e) {
      /* 隐私模式/配额满时不阻断页面 */
    }
    bus.dispatchEvent(new Event("change"));
  }

  function same(a, b) {
    return String(a || "") === String(b || "");
  }

  var store = {
    KEY: KEY,
    snapshot: function () {
      return JSON.parse(JSON.stringify(data));
    },
    isRead: function (id) { return !!data.read[id]; },
    markRead: function (id) {
      if (!id || data.read[id]) return;
      data.read[id] = Date.now();
      persist();
    },
    markUnread: function (id) {
      if (!id || !data.read[id]) return;
      delete data.read[id];
      persist();
    },
    markAllRead: function (ids) {
      var changed = false;
      (ids || []).forEach(function (id) {
        if (!data.read[id]) { data.read[id] = Date.now(); changed = true; }
      });
      if (changed) persist();
    },
    isBookmarked: function (id) { return !!data.bookmark[id]; },
    toggleBookmark: function (id) {
      if (!id) return false;
      if (data.bookmark[id]) delete data.bookmark[id];
      else data.bookmark[id] = Date.now();
      persist();
      return !!data.bookmark[id];
    },
    getStatus: function (id) { return data.status[id] || ""; },
    setStatus: function (id, status) {
      if (!id) return;
      if (data.status[id] === status) delete data.status[id];
      else data.status[id] = status;
      persist();
    },
    getNote: function (id) { return data.notes[id] || ""; },
    hasNote: function (id) { return !!String(data.notes[id] || "").trim(); },
    setNote: function (id, text) {
      if (!id) return;
      var value = String(text == null ? "" : text).trim();
      if (!value) delete data.notes[id];
      else data.notes[id] = value;
      persist();
    },
    isChecked: function (key) { return !!data.checklist[key]; },
    toggleCheck: function (key) {
      if (!key) return false;
      if (data.checklist[key]) delete data.checklist[key];
      else data.checklist[key] = Date.now();
      persist();
      return !!data.checklist[key];
    },
    theme: function () { return data.theme || "auto"; },
    setTheme: function (theme) {
      if (["auto", "light", "dark"].indexOf(theme) < 0) theme = "auto";
      data.theme = theme;
      persist();
    },
    compact: function () { return !!data.compact; },
    setCompact: function (value) {
      data.compact = !!value;
      persist();
    },
    counts: function () {
      return {
        read: Object.keys(data.read).length,
        bookmarks: Object.keys(data.bookmark).length,
        notes: Object.keys(data.notes).filter(function (id) { return String(data.notes[id] || "").trim(); }).length,
        checklist: Object.keys(data.checklist).length
      };
    },
    bookmarkedIds: function () { return Object.keys(data.bookmark); },
    notedIds: function () {
      return Object.keys(data.notes).filter(function (id) { return String(data.notes[id] || "").trim(); });
    },
    statusIds: function (status) {
      return Object.keys(data.status).filter(function (id) { return data.status[id] === status; });
    },
    exportJSON: function () {
      return JSON.stringify({
        app: "merge2-radar",
        exportedAt: new Date().toISOString(),
        data: data
      }, null, 2);
    },
    importJSON: function (text) {
      var parsed = JSON.parse(text);
      var incoming = parsed && parsed.data ? parsed.data : parsed;
      if (!incoming || typeof incoming !== "object") throw new Error("文件格式不正确");
      var next = JSON.parse(JSON.stringify(DEFAULTS));
      ["read", "bookmark", "status", "notes", "checklist"].forEach(function (key) {
        if (incoming[key] && typeof incoming[key] === "object" && !Array.isArray(incoming[key])) next[key] = incoming[key];
      });
      if (["auto", "light", "dark"].indexOf(incoming.theme) >= 0) next.theme = incoming.theme;
      next.compact = !!incoming.compact;
      data = next;
      persist();
      return store.counts();
    },
    clearPersonal: function () {
      var theme = data.theme;
      var compact = data.compact;
      data = JSON.parse(JSON.stringify(DEFAULTS));
      data.theme = theme;
      data.compact = compact;
      persist();
    },
    onChange: function (fn) { bus.addEventListener("change", fn); },
    offChange: function (fn) { bus.removeEventListener("change", fn); },
    same: same
  };

  App.store = store;
})();
