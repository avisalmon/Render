{% load static %}/* ustrip's service worker (spec §0a.2: offline is a feature).
 *
 * Served from /ustrip/sw.js, not /static/, so its scope is /ustrip/ — it can
 * never intercept babook or מט״צים. Everything outside that scope is none of
 * its business.
 *
 * Strategy, by what the thing is:
 *   - hashed static assets  -> cache first (they are immutable by definition)
 *   - pages under /ustrip/  -> network first, fall back to the last copy
 *   - API GETs              -> network first, fall back to the last copy
 *   - anything not a GET    -> straight to the network, never cached
 *
 * Network-first for pages means online always wins and the family never reads
 * a stale plan; the cache is purely what is left when there is no signal.
 *
 * Writes are deliberately NOT queued. A queued edit that lands hours later,
 * after someone else changed the same stop, is worse than being told now that
 * it did not save (spec §0a.2: queued or refused out loud, never silently
 * lost). Refusing out loud is what this does; the page shows the error.
 *
 * CACHE is derived from the hashed asset URLs below, so a deploy that changes
 * any of them changes the cache name and the old one is dropped on activate.
 */
const ASSETS = [
  "{% static 'ustrip/ustrip.css' %}",
  "{% static 'ustrip/ustrip.js' %}",
  "{% static 'ustrip/manifest.webmanifest' %}",
  "{% static 'ustrip/icon-192.png' %}",
  "{% static 'ustrip/icon-512.png' %}",
];
const CACHE = "ustrip-" + ASSETS.join("|").replace(/[^a-z0-9]+/gi, "").slice(-40);
const OFFLINE_URL = "/ustrip/offline/";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE)
      // addAll is all-or-nothing; one 404 would leave the app with no cache at
      // all, so each asset is added on its own and a miss is survivable.
      .then((cache) => Promise.all(
        ASSETS.concat([OFFLINE_URL]).map((url) => cache.add(url).catch(() => null))
      ))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(
        names.filter((n) => n.startsWith("ustrip-") && n !== CACHE).map((n) => caches.delete(n))
      ))
      .then(() => self.clients.claim())
  );
});

function isStaticAsset(url) {
  return url.origin === self.location.origin && url.pathname.startsWith("/static/");
}

function isOurs(url) {
  return url.origin === self.location.origin && url.pathname.startsWith("/ustrip/");
}

async function networkFirst(request) {
  const cache = await caches.open(CACHE);
  try {
    const response = await fetch(request);
    if (response && response.ok) cache.put(request, response.clone());
    return response;
  } catch (err) {
    const cached = await cache.match(request);
    if (cached) return cached;
    if (request.mode === "navigate") {
      const offline = await cache.match(OFFLINE_URL);
      if (offline) return offline;
    }
    throw err;
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(CACHE);
  const cached = await cache.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response && response.ok) cache.put(request, response.clone());
  return response;
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;              // writes go to the network, always
  const url = new URL(request.url);
  if (isStaticAsset(url)) {
    event.respondWith(cacheFirst(request));
    return;
  }
  if (!isOurs(url)) return;                          // not ustrip's business
  if (url.pathname.startsWith("/ustrip/sw.js")) return;
  event.respondWith(networkFirst(request));
});
