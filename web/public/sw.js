// Minimal service worker pass-through to clear PWA installation criteria
self.addEventListener("install", (event) => {
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
    // Directly pass network requests through without aggressive caching
    // This keeps dynamic network streams like live radio audio playing perfectly
    event.respondWith(fetch(event.request));
});