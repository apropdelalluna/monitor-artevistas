"""
Monitor de Ventas — Artevistas Gallery Barcelona
=================================================
Vigila las páginas de todos los artistas de artevistas.eu
y envía un resumen diario a las 20:00 UTC (22:00 España)
con los cambios detectados, precios de obras y suma total vendido.

Requisitos:
    pip install requests beautifulsoup4 schedule resend

Variables de entorno necesarias (configurar en Render):
    RESEND_API_KEY  → tu API key de resend.com
"""

import hashlib
import time
import difflib
import logging
import json
import os
import re
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

import requests
from bs4 import BeautifulSoup
import schedule
import resend

# ─────────────────────────────────────────────
#  CONFIGURACIÓN
# ─────────────────────────────────────────────

EMAIL_DESTINO  = "apropdelalluna@gmail.com"
HORA_ENVIO     = "20:00"
ARCHIVO_ESTADO = "estado_artevistas.json"

PALABRAS_VENTA = [
    "sold", "vendido", "venut", "no disponible",
    "agotado", "reservado", "out of stock",
]

ARTISTAS = [
    {"nombre": "180 Hilos",                    "url": "https://www.artevistas.eu/artist/180-hilos/"},
    {"nombre": "Akore",                        "url": "https://www.artevistas.eu/artist/akore/"},
    {"nombre": "Alberto Blanchart",            "url": "https://www.artevistas.eu/artist/alberto-blanchart-2/"},
    {"nombre": "Álvaro Gómez-Pantoja",         "url": "https://www.artevistas.eu/artist/alvaro-gomez-pantoja/"},
    {"nombre": "Andrzej Farfulowski",          "url": "https://www.artevistas.eu/artist/andrzej-farfulowski/"},
    {"nombre": "António Azevedo",              "url": "https://www.artevistas.eu/artist/antonio-azevedo/"},
    {"nombre": "Art is Trash – F. de Pájaro",  "url": "https://www.artevistas.eu/artist/art-is-trash-francisco-de-pajaro/"},
    {"nombre": "Ashwan",                       "url": "https://www.artevistas.eu/artist/ashwan/"},
    {"nombre": "Bernard Tartinville",          "url": "https://www.artevistas.eu/artist/460/"},
    {"nombre": "BL2A",                         "url": "https://www.artevistas.eu/artist/bl2a/"},
    {"nombre": "Bran Sólo",                    "url": "https://www.artevistas.eu/artist/bran-solo/"},
    {"nombre": "Carmela Alvarado",             "url": "https://www.artevistas.eu/artist/carmela-alvarado/"},
    {"nombre": "Cesar Biojo",                  "url": "https://www.artevistas.eu/artist/cesar-biojo/"},
    {"nombre": "Charlax",                      "url": "https://www.artevistas.eu/artist/charlax/"},
    {"nombre": "Corentin Huon de Penanster",   "url": "https://www.artevistas.eu/artist/corentin-penanster/"},
    {"nombre": "CuellarRabassa",               "url": "https://www.artevistas.eu/artist/cuellarrabassa-2/"},
    {"nombre": "Daniel Délano",                "url": "https://www.artevistas.eu/artist/daniel-delano/"},
    {"nombre": "Daniele Lipari",               "url": "https://www.artevistas.eu/artist/daniele-lipari/"},
    {"nombre": "El Xupet Negre",               "url": "https://www.artevistas.eu/artist/el-xupet-negre/"},
    {"nombre": "Fèlix Roca",                   "url": "https://www.artevistas.eu/artist/felix-roca/"},
    {"nombre": "Filippo Ioco",                 "url": "https://www.artevistas.eu/artist/filippo-ioco/"},
    {"nombre": "Filthy Freak",                 "url": "https://www.artevistas.eu/artist/filthy-freak/"},
    {"nombre": "Frank Diamond",                "url": "https://www.artevistas.eu/artist/franck-diamond-photography-mysterious-atmosphere-photomontage-barcelona/"},
    {"nombre": "Gil Gelpi",                    "url": "https://www.artevistas.eu/artist/gil-gelpi/"},
    {"nombre": "Hugo Barbié",                  "url": "https://www.artevistas.eu/artist/hugo-barbie-artist-barcelona/"},
    {"nombre": "Irene Bou",                    "url": "https://www.artevistas.eu/artist/irene-bou/"},
    {"nombre": "James Ormiston",               "url": "https://www.artevistas.eu/artist/james-ormiston/"},
    {"nombre": "Javier de Cea",                "url": "https://www.artevistas.eu/artist/javier-de-cea-2/"},
    {"nombre": "Jean-Marc Hild",               "url": "https://www.artevistas.eu/artist/jean-marc-hild/"},
    {"nombre": "Juan Carlos Valdiviezo",       "url": "https://www.artevistas.eu/artist/juan-carlos-valdiviezo-ramirez/"},
    {"nombre": "Julien Deniau aka Unavista",   "url": "https://www.artevistas.eu/artist/julien-deniau-aka-unavista/"},
    {"nombre": "Konair",                       "url": "https://www.artevistas.eu/artist/konair-onergizer-konair-koler/"},
    {"nombre": "Laura Erviti",                 "url": "https://www.artevistas.eu/artist/laura-erviti/"},
    {"nombre": "María Cuéllar",                "url": "https://www.artevistas.eu/artist/maria-cuellar/"},
    {"nombre": "Mark Rox",                     "url": "https://www.artevistas.eu/artist/mark-rox-pop-art-pov/"},
    {"nombre": "Martí Roca Balcells",          "url": "https://www.artevistas.eu/artist/marti-roca/"},
    {"nombre": "Matthieu Kowad",               "url": "https://www.artevistas.eu/artist/matthieu-kowad/"},
    {"nombre": "Me Lata",                      "url": "https://www.artevistas.eu/artist/me-lata-barcelona-street-art/"},
    {"nombre": "Miquel Serratosa",             "url": "https://www.artevistas.eu/artist/miquel-serratosa/"},
    {"nombre": "Mireia Cifuentes",             "url": "https://www.artevistas.eu/artist/mireia-cifuentes-2/"},
    {"nombre": "Miss Cutcut",                  "url": "https://www.artevistas.eu/artist/miss-cutcut/"},
    {"nombre": "MOWCKA",                       "url": "https://www.artevistas.eu/artist/mowcka/"},
    {"nombre": "Neon Sandwich",                "url": "https://www.artevistas.eu/artist/neon-sandwich/"},
    {"nombre": "Ninon Réo",                    "url": "https://www.artevistas.eu/artist/ninon-reo-artista/"},
    {"nombre": "Orson Buch",                   "url": "https://www.artevistas.eu/artist/orson-buch/"},
    {"nombre": "Ortaire de Coupigny",          "url": "https://www.artevistas.eu/artist/ortaire-de-coupigny/"},
    {"nombre": "Oscar Gartín",                 "url": "https://www.artevistas.eu/artist/oscar-gartin/"},
    {"nombre": "Pepe Pujol Carabantes",        "url": "https://www.artevistas.eu/artist/pepe-pujol-carabantes/"},
    {"nombre": "Peta Rodríguez",               "url": "https://www.artevistas.eu/artist/peta/"},
    {"nombre": "Peter Doherty",                "url": "https://www.artevistas.eu/artist/peter-doherty/"},
    {"nombre": "Pol Ballonga",                 "url": "https://www.artevistas.eu/artist/pol-ballonga-montoliu/"},
    {"nombre": "Ramón Pons",                   "url": "https://www.artevistas.eu/artist/ramon-pons/"},
    {"nombre": "Reb.MWC",                      "url": "https://www.artevistas.eu/artist/reb-mwc/"},
    {"nombre": "Rémi Boudeperche",             "url": "https://www.artevistas.eu/artist/remi-boudeperche/"},
    {"nombre": "Sandra Partera",               "url": "https://www.artevistas.eu/artist/sandra-partera/"},
    {"nombre": "Santo",                        "url": "https://www.artevistas.eu/artist/santo/"},
    {"nombre": "Sanz i Vila",                  "url": "https://www.artevistas.eu/artist/sanz-i-vila/"},
    {"nombre": "Sater",                        "url": "https://www.artevistas.eu/artist/sater/"},
    {"nombre": "Sergi Muñoz Lozano",           "url": "https://www.artevistas.eu/artist/sergi-munoz-lozano/"},
    {"nombre": "Street Cyber",                 "url": "https://www.artevistas.eu/artist/street-cyber/"},
    {"nombre": "Tempe Hernández",              "url": "https://www.artevistas.eu/artist/tempe-hernandez/"},
    {"nombre": "The Catman",                   "url": "https://www.artevistas.eu/artist/the-catman/"},
    {"nombre": "Tim Marsh",                    "url": "https://www.artevistas.eu/artist/tim-marsh/"},
    {"nombre": "Toni Riera",                   "url": "https://www.artevistas.eu/artist/toni-riera/"},
    {"nombre": "Vaidehi Kinkhabwala",          "url": "https://www.artevistas.eu/artist/vaidehi-kinkhabwala/"},
    {"nombre": "White Rabbit",                 "url": "https://www.artevistas.eu/artist/white-rabbit-revolution/"},
    {"nombre": "Xavi Mira",                    "url": "https://www.artevistas.eu/artist/xavi-mira/"},
    {"nombre": "Xavier Krauel",                "url": "https://www.artevistas.eu/artist/xavier-krauel/"},
    {"nombre": "Yoshbott",                     "url": "https://www.artevistas.eu/artist/yoshbott/"},
    {"nombre": "Yoshihito Suzuki",             "url": "https://www.artevistas.eu/artist/yoshihito-suzuki/"},
    {"nombre": "Zach Oreo",                    "url": "https://www.artevistas.eu/artist/zach-oreo-tpk/"},
    {"nombre": "ZZZ – Various Artists",        "url": "https://www.artevistas.eu/artist/zzz-various-artists/"},
]

# ─────────────────────────────────────────────
#  FIN DE CONFIGURACIÓN
# ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler("monitor_artevistas.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

estado: dict = {}
cambios_del_dia: list = []


# ── Servidor HTTP mínimo para mantener Render activo ──

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Monitor Artevistas activo OK")

    def log_message(self, format, *args):
        pass

def iniciar_servidor_http():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logging.info("Servidor HTTP activo en puerto %d", port)
    server.serve_forever()


# ── Resend ────────────────────────────────────

def inicializar_resend() -> bool:
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        logging.error("❌ Variable RESEND_API_KEY no encontrada.")
        return False
    resend.api_key = api_key
    return True


def enviar_email(asunto: str, cuerpo_html: str) -> None:
    try:
        resend.Emails.send({
            "from":    "Monitor Artevistas <onboarding@resend.dev>",
            "to":      [EMAIL_DESTINO],
            "subject": asunto,
            "html":    cuerpo_html,
        })
        logging.info("✅ Email enviado a %s", EMAIL_DESTINO)
    except Exception as e:
        logging.error("Error al enviar email: %s", e)


# ── Persistencia ──────────────────────────────

def cargar_estado() -> None:
    global estado
    if os.path.exists(ARCHIVO_ESTADO):
        try:
            with open(ARCHIVO_ESTADO, "r", encoding="utf-8") as f:
                estado = json.load(f)
            logging.info("Estado cargado: %d artistas.", len(estado))
        except (json.JSONDecodeError, OSError) as e:
            logging.warning("No se pudo cargar el estado: %s", e)
            estado = {}


def guardar_estado() -> None:
    try:
        with open(ARCHIVO_ESTADO, "w", encoding="utf-8") as f:
            json.dump(estado, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logging.error("No se pudo guardar el estado: %s", e)


# ── Scraping ──────────────────────────────────

def precio_a_numero(precio_str: str) -> float:
    """Convierte '1.200,00€' o '1,200.00€' a float."""
    try:
        limpio = re.sub(r"[^\d.,]", "", precio_str)
        # Formato europeo: 1.200,00
        if "," in limpio and "." in limpio:
            limpio = limpio.replace(".", "").replace(",", ".")
        elif "," in limpio:
            limpio = limpio.replace(",", ".")
        return float(limpio)
    except Exception:
        return 0.0


def extraer_obras(soup: BeautifulSoup) -> dict:
    """Extrae {titulo: {precio, precio_num, estado}} de la página de un artista."""
    obras = {}
    productos = soup.select("li.product, ul.products li")
    for producto in productos:
        titulo_el = (
            producto.select_one(".woocommerce-loop-product__title")
            or producto.select_one("h2")
            or producto.select_one("h3")
        )
        titulo = titulo_el.get_text(strip=True) if titulo_el else "Sin título"

        precio_el = producto.select_one(".woocommerce-Price-amount")
        precio_str = precio_el.get_text(strip=True) if precio_el else "Precio no disponible"
        precio_num = precio_a_numero(precio_str)

        sold = producto.select_one(".sold_out_badge, .out-of-stock")
        estado_obra = "vendido" if sold else "disponible"

        obras[titulo] = {
            "precio":     precio_str,
            "precio_num": precio_num,
            "estado":     estado_obra,
        }
    return obras


def obtener_contenido(artista: dict) -> dict | None:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; MonitorArtevistas/1.0)"}
        resp = requests.get(artista["url"], headers=headers, timeout=20)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        zona = soup.select_one(".products") or soup.select_one("main") or soup.body
        texto = zona.get_text(separator="\n", strip=True)
        hash_actual = hashlib.md5(texto.encode()).hexdigest()
        obras = extraer_obras(soup)

        return {"texto": texto, "hash": hash_actual, "obras": obras}

    except requests.RequestException as e:
        logging.error("[%s] Error: %s", artista["nombre"], e)
        return None


# ── Análisis de cambios ───────────────────────

def detectar_cambios_obras(obras_nuevas: dict, obras_viejas: dict) -> list:
    cambios = []
    for titulo, info_vieja in obras_viejas.items():
        if titulo not in obras_nuevas:
            cambios.append({
                "tipo":       "desaparecida",
                "titulo":     titulo,
                "precio":     info_vieja["precio"],
                "precio_num": info_vieja.get("precio_num", 0.0),
            })
        else:
            info_nueva = obras_nuevas[titulo]
            if info_vieja["estado"] != info_nueva["estado"] and info_nueva["estado"] == "vendido":
                cambios.append({
                    "tipo":       "vendida",
                    "titulo":     titulo,
                    "precio":     info_vieja["precio"],
                    "precio_num": info_vieja.get("precio_num", 0.0),
                })
    for titulo, info_nueva in obras_nuevas.items():
        if titulo not in obras_viejas:
            cambios.append({
                "tipo":       "nueva",
                "titulo":     titulo,
                "precio":     info_nueva["precio"],
                "precio_num": info_nueva.get("precio_num", 0.0),
            })
    return cambios


def generar_diff(texto_viejo: str, texto_nuevo: str) -> str:
    diff = list(difflib.unified_diff(
        texto_viejo.splitlines(),
        texto_nuevo.splitlines(),
        lineterm="", n=2,
    ))
    if not diff:
        return "(sin diferencias)"
    resumen = "\n".join(diff[:60])
    if len(diff) > 60:
        resumen += f"\n... y {len(diff) - 60} líneas más."
    return resumen


# ── Email ─────────────────────────────────────

def construir_bloque(cambio: dict) -> str:
    artista       = cambio["artista"]
    hora          = cambio["hora"]
    cambios_obras = cambio.get("cambios_obras", [])
    diff          = cambio["diff"]

    filas_obras = ""
    for c in cambios_obras:
        if c["tipo"] == "vendida":
            icono, etiqueta, color = "🔴", "Vendida", "#c0392b"
        elif c["tipo"] == "desaparecida":
            icono, etiqueta, color = "🟠", "Desaparecida", "#e67e22"
        else:
            icono, etiqueta, color = "🟢", "Nueva obra", "#27ae60"

        filas_obras += f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #eee;">
            {icono} <strong style="color:{color};">{etiqueta}</strong>
          </td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{c['titulo']}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;font-weight:bold;">{c['precio']}</td>
        </tr>"""

    tabla_obras = ""
    if filas_obras:
        tabla_obras = f"""
        <table style="width:100%;border-collapse:collapse;margin:12px 0;font-size:14px;">
          <thead>
            <tr style="background:#f4f4f4;">
              <th style="padding:8px;text-align:left;">Estado</th>
              <th style="padding:8px;text-align:left;">Obra</th>
              <th style="padding:8px;text-align:left;">Precio</th>
            </tr>
          </thead>
          <tbody>{filas_obras}</tbody>
        </table>"""

    return f"""
    <div style="border:1px solid #e0e0e0;border-radius:10px;padding:18px;margin-bottom:18px;">
      <h3 style="margin:0 0 6px;color:#1a1a2e;">🎨 {artista['nombre']}</h3>
      <p style="margin:0 0 8px;font-size:13px;color:#666;">
        Detectado a las <strong>{hora}</strong> ·
        <a href="{artista['url']}" style="color:#2980b9;">{artista['url']}</a>
      </p>
      {tabla_obras}
      <details style="margin-top:10px;">
        <summary style="cursor:pointer;color:#555;font-size:13px;">Ver diferencias completas</summary>
        <pre style="background:#f8f8f8;padding:12px;border-radius:6px;
                    overflow-x:auto;font-size:11px;margin-top:8px;
                    border-left:3px solid #bbb;">{diff}</pre>
      </details>
    </div>"""


def calcular_resumen_ventas(cambios: list) -> tuple:
    """Devuelve (total_vendido, num_obras_vendidas) de todos los cambios del día."""
    total = 0.0
    num_obras = 0
    for cambio in cambios:
        for c in cambio.get("cambios_obras", []):
            if c["tipo"] in ("vendida", "desaparecida"):
                total += c.get("precio_num", 0.0)
                num_obras += 1
    return total, num_obras


def enviar_resumen_diario() -> None:
    global cambios_del_dia
    ahora = datetime.now().strftime("%d/%m/%Y")

    if not cambios_del_dia:
        asunto = f"🖼️ Artevistas {ahora} — Sin cambios hoy"
        cuerpo = f"""
        <html><body style="font-family:Arial,sans-serif;max-width:700px;margin:auto;padding:24px;">
          <h2 style="border-bottom:2px solid #27ae60;padding-bottom:10px;">
            🖼️ Resumen Artevistas — {ahora}
          </h2>
          <p style="font-size:16px;color:#27ae60;">
            ✅ <strong>Sin cambios detectados hoy</strong> en ninguno de los
            {len(ARTISTAS)} artistas vigilados.
          </p>
          <small style="color:#aaa;">Próximo resumen mañana a las 22:00 h (hora española)</small>
        </body></html>"""
    else:
        n = len(cambios_del_dia)
        total_vendido, num_obras = calcular_resumen_ventas(cambios_del_dia)
        bloques = "".join(construir_bloque(c) for c in cambios_del_dia)

        # Caja resumen de ventas
        if total_vendido > 0:
            resumen_ventas_html = f"""
            <div style="background:#1a1a2e;color:white;border-radius:10px;
                        padding:20px;margin-bottom:24px;text-align:center;">
              <p style="margin:0;font-size:14px;opacity:0.8;">Total vendido hoy</p>
              <p style="margin:8px 0;font-size:36px;font-weight:bold;">
                {total_vendido:,.0f} €
              </p>
              <p style="margin:0;font-size:14px;opacity:0.8;">
                {num_obras} obra{'s' if num_obras > 1 else ''} vendida{'s' if num_obras > 1 else ''}
              </p>
            </div>"""
        else:
            resumen_ventas_html = ""

        asunto = f"🖼️ Artevistas {ahora} — {n} cambio{'s' if n > 1 else ''} detectado{'s' if n > 1 else ''}"
        cuerpo = f"""
        <html><body style="font-family:Arial,sans-serif;max-width:700px;margin:auto;padding:24px;">
          <h2 style="border-bottom:2px solid #2980b9;padding-bottom:10px;">
            🖼️ Resumen Artevistas — {ahora}
          </h2>
          {resumen_ventas_html}
          <p style="font-size:15px;color:#555;">
            Cambios detectados en <strong>{n} artista{'s' if n > 1 else ''}</strong>:
          </p>
          {bloques}
          <small style="color:#aaa;">Próximo resumen mañana a las 22:00 h (hora española)</small>
        </body></html>"""

    enviar_email(asunto, cuerpo)
    cambios_del_dia = []


# ── Comprobación ──────────────────────────────

def comprobar_todos() -> None:
    logging.info("─" * 50)
    logging.info("Comprobando %d artistas...", len(ARTISTAS))

    for artista in ARTISTAS:
        resultado = obtener_contenido(artista)
        if resultado is None:
            continue

        nombre      = artista["nombre"]
        hash_nuevo  = resultado["hash"]
        texto_nuevo = resultado["texto"]
        obras_nuevas = resultado["obras"]

        if nombre not in estado:
            estado[nombre] = {
                "hash":  hash_nuevo,
                "texto": texto_nuevo,
                "obras": obras_nuevas,
            }
            logging.info("[%s] Estado inicial guardado (%d obras).", nombre, len(obras_nuevas))
            continue

        if hash_nuevo == estado[nombre]["hash"]:
            logging.info("[%s] Sin cambios.", nombre)
            continue

        logging.info("[%s] ⚠️  CAMBIO DETECTADO", nombre)
        texto_viejo  = estado[nombre]["texto"]
        obras_viejas = estado[nombre].get("obras", {})

        cambios_obras = detectar_cambios_obras(obras_nuevas, obras_viejas)
        diff = generar_diff(texto_viejo, texto_nuevo)

        cambios_del_dia.append({
            "artista":       artista,
            "diff":          diff,
            "cambios_obras": cambios_obras,
            "hora":          datetime.now().strftime("%H:%M"),
        })

        estado[nombre] = {
            "hash":  hash_nuevo,
            "texto": texto_nuevo,
            "obras": obras_nuevas,
        }

    guardar_estado()
    logging.info("Comprobación finalizada. Cambios acumulados hoy: %d", len(cambios_del_dia))


# ── Main ──────────────────────────────────────

def main() -> None:
    logging.info("=" * 55)
    logging.info("Monitor Artevistas iniciado")
    logging.info("Artistas vigilados : %d", len(ARTISTAS))
    logging.info("Email destino      : %s", EMAIL_DESTINO)
    logging.info("Resumen diario     : %s UTC (22:00 España)", HORA_ENVIO)
    logging.info("=" * 55)

    if not inicializar_resend():
        logging.error("Abortando: falta RESEND_API_KEY.")
        return

    hilo = threading.Thread(target=iniciar_servidor_http, daemon=True)
    hilo.start()

    cargar_estado()
    comprobar_todos()

    schedule.every(2).hours.do(comprobar_todos)
    schedule.every().day.at(HORA_ENVIO).do(enviar_resumen_diario)

    logging.info("Scheduler activo. Próximo email a las 20:00 UTC (22:00 España).")

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
