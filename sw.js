const CACHE_NAME = 'ark-knowledge-base-v5';

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    if (event.request.method !== 'GET') return;

    const url = new URL(event.request.url);

    // data/ 下资源：永远走网络，绕过浏览器 HTTP cache。
    // cache: 'no-store' 让每次 fetch 都直击源站，读到 GitHub Pages 最新内容。
    // 仅在网络挂了时用 SW 缓存兜底（离线浏览已加载过的条目）。
    if (url.pathname.startsWith('/data/')) {
        event.respondWith(
            fetch(event.request, { cache: 'no-store' })
                .then((response) => {
                    if (response.ok) {
                        const responseClone = response.clone();
                        caches.open(CACHE_NAME).then((cache) => {
                            cache.put(event.request, responseClone);
                        });
                    }
                    return response;
                })
                .catch(() => {
                    return caches.match(event.request);
                })
        );
    } else {
        event.respondWith(
            caches.match(event.request).then((cachedResponse) => {
                const fetchPromise = fetch(event.request, { cache: 'no-cache' }).then((networkResponse) => {
                    if (networkResponse.ok && (event.request.url.includes('index.html') || event.request.url.includes('manifest.json') || event.request.url.endsWith('.html'))) {
                        caches.open(CACHE_NAME).then((cache) => {
                            cache.put(event.request, networkResponse.clone());
                        });
                    }
                    return networkResponse;
                }).catch(() => cachedResponse);
                return cachedResponse || fetchPromise;
            })
        );
    }
});
