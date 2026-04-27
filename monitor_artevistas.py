"""
Monitor de Ventas — Artevistas Gallery Barcelona
=================================================
Vigila las páginas de todos los artistas de artevistas.eu
y envía un resumen diario a las 20:00 h con los cambios detectados.

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

# ── Todos los artistas de artevistas.eu ───────
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
        pass  # silenciar logs del servidor HTTP

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

def obtener_contenido(artista: dict) -> tuple | None:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; MonitorArtevistas/1.0)"}
        resp = requests.get(artista["url"], headers=headers, timeout=20)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        zona = (
            soup.select_one(".products")
            or soup.select_one("main")
            or soup.body
        )
        texto = zona.get_text(separator="\n", strip=True)
        return texto, hashlib.md5(texto.encode()).hexdigest()

    except requests.RequestException as e:
        logging.error("[%s] Error: %s", artista["nombre"], e)
        return None


# ── Análisis ──────────────────────────────────

def detectar_palabras_venta(texto_nuevo: str, texto_viejo: str) -> list:
    lineas_nuevas = set(texto_nuevo.splitlines()) - set(texto_viejo.splitlines())
    encontradas = []
    for linea in lineas_nuevas:
        for palabra in PALABRAS_VENTA:
            if palabra.lower() in linea.lower():
                encontradas.append(linea.strip())
                break
    return encontradas


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
    artista = cambio["artista"]
    ventas  = cambio["ventas"]
    diff    = cambio["diff"]
    hora    = cambio["hora"]

    ventas_html = ""
    if ventas:
        items = "".join(f"<li style='margin:4px 0'>{v}</li>" for v in ventas)
        ventas_html = f"""
        <div style="background:#fdecea;padding:10px 14px;border-radius:6px;margin:10px 0;">
          <strong style="color:#c0392b;">🔴 Posibles ventas:</strong>
          <ul style="font-family:monospace;margin:6px 0;padding-left:18px;">{items}</ul>
        </div>"""

    return f"""
    <div style="border:1px solid #e0e0e0;border-radius:10px;padding:18px;margin-bottom:18px;">
      <h3 style="margin:0 0 6px;color:#1a1a2e;">🎨 {artista['nombre']}</h3>
      <p style="margin:0 0 4px;font-size:13px;color:#666;">
        Detectado a las <strong>{hora}</strong> ·
        <a href="{artista['url']}" style="color:#2980b9;">{artista['url']}</a>
      </p>
      {ventas_html}
      <details style="margin-top:10px;">
        <summary style="cursor:pointer;color:#555;font-size:13px;">Ver diferencias</summary>
        <pre style="background:#f8f8f8;padding:12px;border-radius:6px;
                    overflow-x:auto;font-size:11px;margin-top:8px;
                    border-left:3px solid #bbb;">{diff}</pre>
      </details>
    </div>"""


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
          <small style="color:#aaa;">Próximo resumen mañana a las {HORA_ENVIO}</small>
        </body></html>"""
    else:
        n = len(cambios_del_dia)
        bloques = "".join(construir_bloque(c) for c in cambios_del_dia)
        asunto = f"🖼️ Artevistas {ahora} — {n} cambio{'s' if n > 1 else ''} detectado{'s' if n > 1 else ''}"
        cuerpo = f"""
        <html><body style="font-family:Arial,sans-serif;max-width:700px;margin:auto;padding:24px;">
          <h2 style="border-bottom:2px solid #2980b9;padding-bottom:10px;">
            🖼️ Resumen Artevistas — {ahora}
          </h2>
          <p style="font-size:15px;color:#555;">
            Cambios en <strong>{n} artista{'s' if n > 1 else ''}</strong> hoy.
          </p>
          {bloques}
          <small style="color:#aaa;">Próximo resumen mañana a las {HORA_ENVIO}</small>
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

        texto_nuevo, hash_nuevo = resultado
        nombre = artista["nombre"]

        if nombre not in estado:
            estado[nombre] = {"hash": hash_nuevo, "texto": texto_nuevo}
            logging.info("[%s] Estado inicial guardado.", nombre)
            continue

        if hash_nuevo == estado[nombre]["hash"]:
            logging.info("[%s] Sin cambios.", nombre)
            continue

        logging.info("[%s] ⚠️  CAMBIO DETECTADO", nombre)
        texto_viejo = estado[nombre]["texto"]

        cambios_del_dia.append({
            "artista": artista,
            "diff":    generar_diff(texto_viejo, texto_nuevo),
            "ventas":  detectar_palabras_venta(texto_nuevo, texto_viejo),
            "hora":    datetime.now().strftime("%H:%M"),
        })

        estado[nombre] = {"hash": hash_nuevo, "texto": texto_nuevo}

    guardar_estado()
    logging.info("Comprobación finalizada. Cambios acumulados hoy: %d", len(cambios_del_dia))


# ── Main ──────────────────────────────────────

def main() -> None:
    logging.info("=" * 55)
    logging.info("Monitor Artevistas iniciado")
    logging.info("Artistas vigilados : %d", len(ARTISTAS))
    logging.info("Email destino      : %s", EMAIL_DESTINO)
    logging.info("Resumen diario     : %s", HORA_ENVIO)
    logging.info("=" * 55)

    if not inicializar_resend():
        logging.error("Abortando: falta RESEND_API_KEY.")
        return

    # Iniciar servidor HTTP en hilo separado para mantener Render activo
    hilo = threading.Thread(target=iniciar_servidor_http, daemon=True)
    hilo.start()

    cargar_estado()
    comprobar_todos()

    schedule.every(2).hours.do(comprobar_todos)
    schedule.every().day.at(HORA_ENVIO).do(enviar_resumen_diario)

    logging.info("Scheduler activo. Próximo email a las %s.", HORA_ENVIO)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
