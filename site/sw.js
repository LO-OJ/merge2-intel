/* 二合情报站 · 离线缓存（仅 http/https 生效，GitHub Pages 可用） */
const CACHE = "merge2-radar-v1";
const CORE = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./assets/css/app.css",
  "./assets/icons/icon.svg",
  "./assets/js/util.js",
  "./assets/js/icons.js",
  "./assets/js/store.js",
  "./assets/js/components.js",
  "./assets/js/router.js",
  "./assets/js/views/home.js",
  "./assets/js/views/feed.js",
  "./assets/js/views/games.js",
  "./assets/js/views/game.js",
  "./assets/js/views/matrix.js",
  "./assets/js/views/playbook.js",
  "./assets/js/views/versions.js",
  "./assets/js/views/radar.js",
  "./assets/js/views/digest.js",
  "./assets/js/views/sources.js",
  "./assets/js/views/notes.js",
  "./assets/js/views/settings.js",
  "./assets/js/app.js"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => Promise.allSettled(CORE.map((url) => cache.add(url)))).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)))).then(() => self.clients.claim())
  );
});

function networkFirst(request, fallbackUrl) {
  return fetch(request)
    .then((response) => {
      if (response && response.ok) {
        const copy = response.clone();
        caches.open(CACHE).then((cache) => cache.put(request, copy)).catch(() => {});
      }
      return response;
    })
    .catch(() => caches.match(request).then((cached) => cached || (fallbackUrl ? caches.match(fallbackUrl) : null)));
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith(networkFirst(request, "./index.html"));
    return;
  }
  if (url.pathname.includes("/data/")) {
    event.respondWith(networkFirst(request));
    return;
  }
  event.respondWith(
    caches.match(request).then((cached) => cached || fetch(request).then((response) => {
      if (response && response.ok) {
        const copy = response.clone();
        caches.open(CACHE).then((cache) => cache.put(request, copy)).catch(() => {});
      }
      return response;
    }).catch(() => caches.match("./index.html")))
  );
});
