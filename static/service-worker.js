const CACHE = 'caltracker-v1';
const STATIC = ['/static/style.css', '/static/manifest.json', '/static/icon.svg'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(STATIC)));
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(clients.claim());
});

self.addEventListener('fetch', (e) => {
  const { request } = e;
  if (request.method !== 'GET') return;
  e.respondWith(
    caches.match(request).then((hit) => hit || fetch(request).then((r) => {
      if (request.url.startsWith(self.location.origin) && STATIC.includes(new URL(request.url).pathname)) {
        const copy = r.clone();
        caches.open(CACHE).then((c) => c.put(request, copy));
      }
      return r;
    }))
  );
});
