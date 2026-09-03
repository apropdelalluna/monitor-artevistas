// Service worker mínimo — solo para cumplir el requisito de Chrome que
// permite instalar la web como app ("Añadir a pantalla de inicio").
// No cachea nada a propósito: los datos (ventas, estado, alertas) vienen
// siempre en vivo desde GitHub, y no queremos arriesgarnos a mostrar
// datos desactualizados por una caché.

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  // Passthrough puro: deja pasar todas las peticiones tal cual, sin cachear.
  event.respondWith(fetch(event.request));
});
