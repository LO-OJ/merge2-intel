/* 二合情报站 · 启动 */
(function () {
  "use strict";
  var App = (window.App = window.App || {});

  function fatal(message) {
    var main = document.getElementById("main");
    if (!main) return;
    main.innerHTML = "";
    main.appendChild(App.h("div", { class: "empty-state fatal" }, [
      App.icon("alert", "empty-icon"),
      App.h("h3", null, "站点数据没有加载"),
      App.h("p", null, message),
      App.h("p", { class: "muted" }, "在项目根目录运行：python tools/build.py，然后刷新页面。")
    ]));
  }

  App.loadCharts = function (callback) {
    if (App.charts) { callback(true); return; }
    if (App._chartsLoading) { App._chartsQueue.push(callback); return; }
    App._chartsLoading = true;
    App._chartsQueue = [callback];
    var script = document.createElement("script");
    var build = (App.meta() || {}).buildId || "1";
    script.src = "./data/charts.js?v=" + encodeURIComponent(build);
    script.onload = function () {
      App.charts = window.KB_CHARTS || null;
      App._chartsLoading = false;
      var queue = App._chartsQueue || [];
      App._chartsQueue = [];
      queue.forEach(function (fn) { try { fn(!!App.charts); } catch (e) { console.error(e); } });
    };
    script.onerror = function () {
      App._chartsLoading = false;
      var queue = App._chartsQueue || [];
      App._chartsQueue = [];
      queue.forEach(function (fn) { try { fn(false); } catch (e) { console.error(e); } });
    };
    document.head.appendChild(script);
  };

  function boot() {
    App.KB = window.KB;
    if (!App.KB || !App.KB.meta) {
      fatal("找不到 window.KB。请先运行构建脚本生成 site/data/kb.js。");
      return;
    }
    App.comp.renderShell();
    App.router.start();

    if ("serviceWorker" in navigator && (location.protocol === "http:" || location.protocol === "https:")) {
      navigator.serviceWorker.register("./sw.js").catch(function (error) {
        console.warn("Service worker 未注册：", error && error.message);
      });
    }

    if (window.matchMedia) {
      var mq = window.matchMedia("(prefers-color-scheme: dark)");
      var onChange = function () { if (App.store.theme() === "auto") App.comp.applyTheme(); };
      if (mq.addEventListener) mq.addEventListener("change", onChange);
      else if (mq.addListener) mq.addListener(onChange);
    }

    document.addEventListener("keydown", function (event) {
      var tag = (event.target && event.target.tagName || "").toLowerCase();
      var typing = tag === "input" || tag === "textarea" || tag === "select" || (event.target && event.target.isContentEditable);
      if (event.key === "/" && !typing && !event.metaKey && !event.ctrlKey && !event.altKey) {
        event.preventDefault();
        var search = document.querySelector(".top-search-input");
        if (search) search.focus();
      }
      if (event.key === "Escape") {
        var sidebar = document.getElementById("sidebar");
        var overlay = document.getElementById("nav-overlay");
        var sheet = document.getElementById("more-sheet");
        if (sidebar) sidebar.classList.remove("is-open");
        if (overlay) overlay.classList.remove("is-on");
        if (sheet) sheet.classList.remove("is-on");
      }
    });

    if (App.store) {
      App.store.onChange(function () {
        // 顶栏数据不变；个人状态变化由具体视图自行刷新
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
