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
  // Solo intervenir en peticiones hacia la propia web — cualquier petición
  // a otro dominio (GitHub, Render, fuentes, etc.) se deja pasar sin tocar,
  // exactamente como si no hubiera service worker de por medio. Interceptar
  // peticiones cruzadas (sobre todo las especiales tipo 'no-cors', como la
  // del botón de "Despertar servicio") puede romperlas silenciosamente.
  if (new URL(event.request.url).origin !== self.location.origin) {
    return;
  }
  event.respondWith(fetch(event.request));
});
