
"use strict";

const CACHE_NAME = "basketbol-pwa-v1";

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();

      await Promise.all(
        keys
          .filter((key) => key.startsWith("basketbol-pwa-") && key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      );

      await self.clients.claim();
    })()
  );
});

// Ağ isteklerini değiştirmiyoruz; tahmin verilerinin güncel kalmasını sağlıyoruz.
self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
});
