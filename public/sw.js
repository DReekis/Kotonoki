const CACHE_NAME = 'kotonoki-v4';
const STATIC_ASSETS = [
  '/',
  '/static/css/tokens.css',
  '/static/css/explorer.css',
  '/static/css/sticky.css',
  '/static/js/htmx.min.js',
  '/static/icons/icon-192.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(STATIC_ASSETS).catch(() => {});
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
    ))
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  // 1. Only intercept GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  // 2. Only intercept same-origin requests (ignore chrome-extension, CDNs, etc.)
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) {
    return;
  }

  // 3. Network first for HTML navigation
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(() => caches.match(event.request))
    );
    return;
  }

  // 4. Cache first for static assets, network fallback
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(event.request).then(cached => cached || fetch(event.request))
    );
    return;
  }
});
