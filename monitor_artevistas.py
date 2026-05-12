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
HORA_ENVIO     = "18:00"
ARCHIVO_ESTADO   = "estado_artevistas.json"
ARCHIVO_MENSUAL  = "ventas_mensuales.json"
ARCHIVO_HISTORIAL = "historial_cambios.json"

# GitHub
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO  = "apropdelalluna/monitor-artevistas"
GITHUB_API   = "https://api.github.com"

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
        github_guardar_archivo(ARCHIVO_ESTADO)
        # Guardar meta separado con hora de última comprobación
        meta = {"ultima_comprobacion": datetime.now().strftime("%d/%m/%Y %H:%M")}
        with open("meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)
        github_guardar_archivo("meta.json")
    except OSError as e:
        logging.error("No se pudo guardar el estado: %s", e)


def github_guardar_archivo(nombre_archivo: str) -> None:
    """Sube un archivo JSON al repositorio de GitHub para persistirlo."""
    if not GITHUB_TOKEN:
        logging.warning("GITHUB_TOKEN no configurado, no se guarda en GitHub.")
        return
    try:
        with open(nombre_archivo, "r", encoding="utf-8") as f:
            contenido = f.read()

        import base64
        contenido_b64 = base64.b64encode(contenido.encode("utf-8")).decode("utf-8")

        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }
        url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{nombre_archivo}"

        # Obtener SHA actual del archivo si existe
        sha = None
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            sha = r.json().get("sha")

        payload = {
            "message": f"Monitor: actualizar {nombre_archivo} [{datetime.now().strftime('%d/%m/%Y %H:%M')}] [skip ci]",
            "content": contenido_b64,
        }
        if sha:
            payload["sha"] = sha

        r = requests.put(url, headers=headers, json=payload, timeout=15)
        if r.status_code in (200, 201):
            logging.info("✅ %s guardado en GitHub.", nombre_archivo)
        else:
            logging.error("Error guardando en GitHub: %s %s", r.status_code, r.text[:200])

    except Exception as e:
        logging.error("Error en github_guardar_archivo: %s", e)


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



def obtener_precio_desde_producto(url_producto: str) -> tuple[str, float]:
    """Extrae el precio de la página individual de una obra via JSON-LD."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "es-ES,es;q=0.9",
    }
    try:
        resp = requests.get(url_producto, headers=headers, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Buscar JSON-LD
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                # Puede ser un objeto o una lista dentro de @graph
                productos = []
                if isinstance(data, dict):
                    if data.get("@type") == "Product":
                        productos.append(data)
                    elif "@graph" in data:
                        productos = [x for x in data["@graph"] if x.get("@type") == "Product"]
                for prod in productos:
                    for offer in prod.get("offers", []):
                        for spec in offer.get("priceSpecification", []):
                            precio_num = float(spec.get("price", 0))
                            if precio_num > 0:
                                moneda = spec.get("priceCurrency", "EUR")
                                precio_str = f"{precio_num:,.2f}€".replace(",", "X").replace(".", ",").replace("X", ".")
                                return precio_str, precio_num
            except Exception:
                continue

    except Exception as e:
        logging.debug("No se pudo obtener precio de %s: %s", url_producto, e)

    return "Precio no disponible", 0.0


def extraer_obras(soup: BeautifulSoup) -> dict:
    """Extrae {url: {titulo, precio, precio_num, estado, url}} de la página de un artista."""
    obras = {}

    # Selectores en orden de especificidad — cubre distintas versiones de WooCommerce/Artevistas
    SELECTORES_PRODUCTO = [
        "li.product",
        "ul.products li",
        "article.product",
        ".wc-block-grid__product",
        ".product-item",
        "[class*='product']",   # cualquier clase que contenga 'product'
    ]

    productos = []
    for sel in SELECTORES_PRODUCTO:
        productos = soup.select(sel)
        if productos:
            logging.debug("Selector '%s' encontró %d productos", sel, len(productos))
            break

    if not productos:
        logging.warning("No se encontraron productos con ningún selector conocido")
        return obras

    for producto in productos:
        # Título: varios selectores posibles
        titulo_el = (
            producto.select_one(".woocommerce-loop-product__title")
            or producto.select_one(".wc-block-grid__product-title")
            or producto.select_one("h2")
            or producto.select_one("h3")
            or producto.select_one(".product-title")
            or producto.select_one("a[aria-label]")
        )
        if titulo_el and titulo_el.name == "a":
            titulo = titulo_el.get("aria-label", titulo_el.get_text(strip=True))
        else:
            titulo = titulo_el.get_text(strip=True) if titulo_el else "Sin título"

        if not titulo or titulo == "Sin título":
            continue  # saltar elementos vacíos / falsos positivos

        # Precio
        precio_el = (
            producto.select_one(".woocommerce-Price-amount")
            or producto.select_one(".price")
            or producto.select_one("[class*='price']")
        )
        precio_str = precio_el.get_text(strip=True) if precio_el else "Precio no disponible"
        # Quedarnos solo con el primer precio si hay rango (ej: "500,00€ – 800,00€")
        precio_str = precio_str.split("–")[0].split("-")[0].strip()
        precio_num = precio_a_numero(precio_str)

        # Estado (vendido / disponible)
        sold = producto.select_one(
            ".sold_out_badge, .out-of-stock, .soldout, .out-of-stock-label, "
            "[class*='sold'], [class*='vendido'], .ribbon"
        )
        # También buscar el texto "sold" / "vendido" en el propio bloque
        texto_producto = producto.get_text(separator=" ", strip=True).lower()
        es_vendido = bool(sold) or any(p in texto_producto for p in PALABRAS_VENTA)
        estado_obra = "vendido" if es_vendido else "disponible"

        # URL de la obra individual — usada como clave única
        url_obra = None
        enlace = producto.select_one("a.woocommerce-LoopProduct-link, a.woocommerce-loop-product__link, .box-image a")
        if enlace and enlace.get("href"):
            url_obra = enlace["href"]

        # Usar URL como clave para evitar sobreescribir duplicados de título
        clave = url_obra if url_obra else titulo

        obras[clave] = {
            "titulo":     titulo,
            "precio":     precio_str,
            "precio_num": precio_num,
            "estado":     estado_obra,
            "url":        url_obra,
        }

    return obras


def obtener_contenido(artista: dict) -> dict | None:
    """Obtiene el contenido de la página de un artista, siguiendo la paginación."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "es-ES,es;q=0.9",
    }
    try:
        obras_totales = {}
        textos = []
        url = artista["url"]
        pagina = 1
        max_paginas = 10  # límite de seguridad

        while url and pagina <= max_paginas:
            resp = requests.get(url, headers=headers, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Zona principal
            zona = soup.select_one(".products") or soup.select_one("main") or soup.body
            textos.append(zona.get_text(separator="\n", strip=True))

            # Extraer obras de esta página
            obras_pagina = extraer_obras(soup)
            obras_totales.update(obras_pagina)

            # Siguiente página
            siguiente = soup.select_one("a.next.page-numbers, .woocommerce-pagination a.next")
            url = siguiente["href"] if siguiente else None
            pagina += 1

        if pagina > 2:
            logging.info("[%s] Paginación: %d páginas, %d obras totales",
                         artista["nombre"], pagina - 1, len(obras_totales))

        texto_completo = "\n".join(textos)
        hash_actual = hashlib.md5(texto_completo.encode()).hexdigest()

        return {"texto": texto_completo, "hash": hash_actual, "obras": obras_totales}

    except requests.RequestException as e:
        logging.error("[%s] Error: %s", artista["nombre"], e)
        return None


# ── Análisis de cambios ───────────────────────

def detectar_cambios_obras(obras_nuevas: dict, obras_viejas: dict) -> list:
    cambios = []
    # Índice de obras nuevas por título para fallback cuando la clave no coincide
    obras_nuevas_por_titulo = {}
    for clave_n, info_n in obras_nuevas.items():
        t = info_n.get("titulo", clave_n)
        if t not in obras_nuevas_por_titulo:
            obras_nuevas_por_titulo[t] = (clave_n, info_n)

    for clave, info_vieja in obras_viejas.items():
        titulo = info_vieja.get("titulo", clave)
        if clave not in obras_nuevas:
            # Intentar encontrar por título como fallback (obras sin URL en estado antiguo)
            match = obras_nuevas_por_titulo.get(titulo)
            if match:
                _, info_nueva = match
                if info_vieja["estado"] != info_nueva["estado"]:
                    if info_nueva["estado"] == "vendido":
                        cambios.append({
                            "tipo":       "vendida",
                            "titulo":     titulo,
                            "precio":     info_vieja["precio"],
                            "precio_num": info_vieja.get("precio_num", 0.0),
                        })
                    elif info_vieja["estado"] == "vendido" and info_nueva["estado"] == "disponible":
                        cambios.append({
                            "tipo":       "nueva",
                            "titulo":     titulo,
                            "precio":     info_nueva["precio"],
                            "precio_num": info_nueva.get("precio_num", 0.0),
                        })
            else:
                cambios.append({
                    "tipo":       "desaparecida",
                    "titulo":     titulo,
                    "precio":     info_vieja["precio"],
                    "precio_num": info_vieja.get("precio_num", 0.0),
                })
        else:
            info_nueva = obras_nuevas[clave]
            if info_vieja["estado"] != info_nueva["estado"]:
                if info_nueva["estado"] == "vendido":
                    cambios.append({
                        "tipo":       "vendida",
                        "titulo":     titulo,
                        "precio":     info_vieja["precio"],
                        "precio_num": info_vieja.get("precio_num", 0.0),
                    })
                elif info_vieja["estado"] == "vendido" and info_nueva["estado"] == "disponible":
                    cambios.append({
                        "tipo":       "nueva",
                        "titulo":     titulo,
                        "precio":     info_nueva["precio"],
                        "precio_num": info_nueva.get("precio_num", 0.0),
                    })

    # Claves del estado viejo que ya se procesaron por título (para no duplicar)
    claves_viejas_titulos = {info.get("titulo", clave) for clave, info in obras_viejas.items()}

    for clave, info_nueva in obras_nuevas.items():
        titulo = info_nueva.get("titulo", clave)
        if clave not in obras_viejas and titulo not in claves_viejas_titulos:
            tipo = "nueva_vendida" if info_nueva.get("estado") == "vendido" else "nueva"
            precio_str = info_nueva["precio"]
            precio_num = info_nueva.get("precio_num", 0.0)

            if tipo == "nueva_vendida" and precio_num == 0.0 and info_nueva.get("url"):
                logging.info("Buscando precio de obra vendida: %s", titulo)
                precio_str, precio_num = obtener_precio_desde_producto(info_nueva["url"])

            cambios.append({
                "tipo":       tipo,
                "titulo":     titulo,
                "precio":     precio_str,
                "precio_num": precio_num,
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
        if c["tipo"] == "desaparecida":
            continue  # No mostrar desaparecidas en el email
        if c["tipo"] == "vendida":
            icono, etiqueta, color = "🔴", "Vendida", "#c0392b"
        elif c["tipo"] == "desaparecida":
            icono, etiqueta, color = "🟠", "Desaparecida", "#e67e22"
        elif c["tipo"] == "nueva_vendida":
            icono, etiqueta, color = "🔴🟢", "Nueva (ya vendida)", "#8e44ad"
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
            if c["tipo"] in ("vendida", "nueva_vendida"):
                total += c.get("precio_num", 0.0)
                num_obras += 1
    return total, num_obras


def construir_bloque_mensual() -> str:
    """Genera el bloque HTML con el resumen de ventas del mes actual e historial."""
    try:
        if not os.path.exists(ARCHIVO_MENSUAL):
            return ""
        with open(ARCHIVO_MENSUAL, "r", encoding="utf-8") as f:
            acumulado = json.load(f)
        mes_actual = datetime.now().strftime("%Y-%m")
        ventas = acumulado.get(mes_actual, [])
        # Filtrar RESERVED y desaparecidas del total
        ventas_reales = [v for v in ventas if not v.get("obra", "").upper().find("RESERVED") >= 0 and v.get("tipo") not in ("desaparecida",)]
        ventas_reales = [v for v in ventas if not "RESERVED" in v.get("obra", "") and v.get("tipo") != "desaparecida"]
        total = sum(v.get("precio_num", 0.0) for v in ventas_reales)
        num = len(ventas_reales)
        MESES_ES = {
            "January": "Enero", "February": "Febrero", "March": "Marzo",
            "April": "Abril", "May": "Mayo", "June": "Junio",
            "July": "Julio", "August": "Agosto", "September": "Septiembre",
            "October": "Octubre", "November": "Noviembre", "December": "Diciembre"
        }
        nombre_mes_en = datetime.now().strftime("%B")
        nombre_mes = MESES_ES.get(nombre_mes_en, nombre_mes_en) + " " + datetime.now().strftime("%Y")

        # Historial de meses anteriores
        historial_html = ""
        meses_anteriores = sorted(
            [m for m in acumulado.keys() if m != mes_actual], reverse=True
        )
        if meses_anteriores:
            filas = ""
            for mes in meses_anteriores:
                ventas_mes = acumulado[mes]
                ventas_mes_reales = [v for v in ventas_mes if not "RESERVED" in v.get("obra", "") and v.get("tipo") != "desaparecida"]
                total_mes = sum(v.get("precio_num", 0.0) for v in ventas_mes_reales)
                num_mes = len(ventas_mes_reales)
                nombre_mes_en = datetime.strptime(mes, "%Y-%m").strftime("%B")
                nombre = MESES_ES.get(nombre_mes_en, nombre_mes_en) + " " + mes.split("-")[0]
                filas += f"""
                <tr>
                  <td style="padding:4px 8px;color:#555;">{nombre}</td>
                  <td style="padding:4px 8px;text-align:center;color:#555;">{num_mes}</td>
                  <td style="padding:4px 8px;text-align:right;color:#555;">{total_mes:,.0f} €</td>
                </tr>"""
            historial_html = f"""
            <table style="width:100%;margin-top:10px;border-collapse:collapse;font-size:13px;">
              <tr style="border-bottom:1px solid #ccc;">
                <th style="padding:4px 8px;text-align:left;color:#888;">Mes</th>
                <th style="padding:4px 8px;text-align:center;color:#888;">Obras</th>
                <th style="padding:4px 8px;text-align:right;color:#888;">Total</th>
              </tr>
              {filas}
            </table>"""

        return f"""
        <div style="background:#f0f4f8;border-left:4px solid #2980b9;
                    border-radius:6px;padding:16px;margin-top:24px;">
          <p style="margin:0 0 8px;font-size:14px;font-weight:bold;color:#2980b9;">
            📊 Ventas acumuladas en {nombre_mes}
          </p>
          <p style="margin:0;font-size:14px;color:#333;">
            🖼️ Obras vendidas: <strong>{num}</strong>
            &nbsp;&nbsp;|&nbsp;&nbsp;
            💰 Total: <strong>{total:,.0f} €</strong>
          </p>
          {historial_html}
        </div>"""
    except Exception:
        return ""


def enviar_resumen_diario() -> None:
    global cambios_del_dia
    ahora = datetime.now().strftime("%d/%m/%Y")

    # Guardar ventas antes de construir el email para que el bloque mensual esté actualizado
    if cambios_del_dia:
        guardar_ventas_mensuales(cambios_del_dia)
        guardar_historial(cambios_del_dia)

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
          {construir_bloque_mensual()}
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
          {construir_bloque_mensual()}
          <small style="color:#aaa;">Próximo resumen mañana a las 22:00 h (hora española)</small>
        </body></html>"""

    enviar_email(asunto, cuerpo)

    cambios_del_dia = []


# ── Resumen mensual ───────────────────────────

def guardar_ventas_mensuales(cambios: list) -> None:
    """Añade las ventas del día al archivo mensual."""
    try:
        if os.path.exists(ARCHIVO_MENSUAL):
            with open(ARCHIVO_MENSUAL, "r", encoding="utf-8") as f:
                acumulado = json.load(f)
        else:
            acumulado = {}

        mes_actual = datetime.now().strftime("%Y-%m")
        if mes_actual not in acumulado:
            acumulado[mes_actual] = []

        fecha_hoy = datetime.now().strftime("%d/%m/%Y")
        for cambio in cambios:
            for c in cambio.get("cambios_obras", []):
                if c["tipo"] in ("vendida", "desaparecida", "nueva_vendida"):
                    acumulado[mes_actual].append({
                        "fecha":      fecha_hoy,
                        "artista":    cambio["artista"]["nombre"],
                        "obra":       c["titulo"],
                        "precio":     c["precio"],
                        "precio_num": c.get("precio_num", 0.0),
                        "tipo":       c["tipo"],
                    })

        with open(ARCHIVO_MENSUAL, "w", encoding="utf-8") as f:
            json.dump(acumulado, f, ensure_ascii=False, indent=2)

        github_guardar_archivo(ARCHIVO_MENSUAL)
        logging.info("Ventas mensuales actualizadas (%s).", mes_actual)
    except Exception as e:
        logging.error("Error guardando ventas mensuales: %s", e)


def buscar_duplicados() -> None:
    """Busca obras con título duplicado comparando URLs — añade las que faltan en ventas_totales."""
    logging.info("🔍 Buscando obras duplicadas por título en páginas de artistas...")

    if not os.path.exists("ventas_totales.json"):
        logging.warning("No existe ventas_totales.json — ejecuta CALCULAR_VENTAS=1 primero.")
        return

    with open("ventas_totales.json", "r", encoding="utf-8") as f:
        resultado = json.load(f)

    total_nuevas = 0

    for artista in ARTISTAS:
        nombre = artista["nombre"]
        contenido = obtener_contenido(artista)
        if contenido is None:
            continue

        obras_web = contenido["obras"]
        obras_estado = estado.get(nombre, {}).get("obras", {})

        # URLs ya registradas en el estado
        urls_registradas = {info["url"] for info in obras_estado.values()}

        for titulo, info in obras_web.items():
            if info["estado"] != "vendido":
                continue
            # Si la URL no está registrada en el estado — es un duplicado no contabilizado
            if info["url"] not in urls_registradas:
                _, precio_num = obtener_precio_desde_producto(info["url"])
                if nombre not in resultado:
                    resultado[nombre] = {"total": 0.0, "obras_vendidas": 0, "obras_con_precio": 0, "detalle": [], "ultima_actualizacion": datetime.now().strftime("%d/%m/%Y %H:%M")}

                # Generar título único
                titulo_unico = titulo
                titulos_existentes = {o["titulo"] for o in resultado[nombre].get("detalle", [])}
                contador = 2
                while titulo_unico in titulos_existentes:
                    titulo_unico = f"{titulo} ({contador})"
                    contador += 1

                resultado[nombre]["detalle"].append({"titulo": titulo_unico, "precio_num": precio_num})
                resultado[nombre]["obras_vendidas"] += 1
                if precio_num > 0:
                    resultado[nombre]["total"] += precio_num
                    resultado[nombre]["obras_con_precio"] += 1
                total_nuevas += 1
                logging.info("  ✅ %s – %s: %.0f€", nombre, titulo_unico, precio_num)
                time.sleep(0.5)

    with open("ventas_totales.json", "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    github_guardar_archivo("ventas_totales.json")
    logging.info("✅ ventas_totales.json actualizado. Obras duplicadas encontradas: %d", total_nuevas)


def buscar_obras_faltantes() -> None:
    """Hace scraping de cada página de artista para encontrar obras SOLD no registradas en el estado."""
    logging.info("🔍 Buscando obras vendidas no registradas en el estado...")

    if not os.path.exists("ventas_totales.json"):
        logging.warning("No existe ventas_totales.json — ejecuta CALCULAR_VENTAS=1 primero.")
        return

    with open("ventas_totales.json", "r", encoding="utf-8") as f:
        resultado = json.load(f)

    total_nuevas = 0

    for artista in ARTISTAS:
        nombre = artista["nombre"]
        contenido = obtener_contenido(artista)
        if contenido is None:
            continue

        obras_web = contenido["obras"]
        obras_estado = estado.get(nombre, {}).get("obras", {})
        detalle_actual = {o["titulo"]: o for o in resultado.get(nombre, {}).get("detalle", [])}

        # Buscar obras SOLD en la web que no están ni en el estado ni en ventas_totales
        for titulo, info in obras_web.items():
            if info["estado"] == "vendido" and titulo not in obras_estado and titulo not in detalle_actual:
                _, precio_num = obtener_precio_desde_producto(info["url"])
                if nombre not in resultado:
                    resultado[nombre] = {"total": 0.0, "obras_vendidas": 0, "obras_con_precio": 0, "detalle": [], "ultima_actualizacion": datetime.now().strftime("%d/%m/%Y %H:%M")}
                resultado[nombre]["detalle"].append({"titulo": titulo, "precio_num": precio_num})
                resultado[nombre]["obras_vendidas"] += 1
                if precio_num > 0:
                    resultado[nombre]["total"] += precio_num
                    resultado[nombre]["obras_con_precio"] += 1
                total_nuevas += 1
                logging.info("  ✅ %s – %s: %.0f€", nombre, titulo, precio_num)
                time.sleep(0.5)

    with open("ventas_totales.json", "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    github_guardar_archivo("ventas_totales.json")
    logging.info("✅ ventas_totales.json actualizado. Obras nuevas encontradas: %d", total_nuevas)


def rellenar_precios_faltantes() -> None:
    """Visita solo las obras sin precio en ventas_totales.json y completa los datos."""
    logging.info("📊 Rellenando precios faltantes en ventas_totales.json...")

    if not os.path.exists("ventas_totales.json"):
        logging.warning("No existe ventas_totales.json — ejecuta CALCULAR_VENTAS=1 primero.")
        return

    with open("ventas_totales.json", "r", encoding="utf-8") as f:
        resultado = json.load(f)

    total_rellenados = 0

    for artista, datos in estado.items():
        if artista == "_meta" or artista not in resultado:
            continue

        obras_estado = datos.get("obras", {})
        detalle_actual = {o["titulo"]: o for o in resultado[artista].get("detalle", [])}
        vendidas = [(titulo, info["url"]) for titulo, info in obras_estado.items() if info["estado"] == "vendido"]

        for titulo, url in vendidas:
            if titulo not in detalle_actual:
                _, precio_num = obtener_precio_desde_producto(url)
                if precio_num > 0:
                    resultado[artista]["detalle"].append({"titulo": titulo, "precio_num": precio_num})
                    resultado[artista]["total"] += precio_num
                    resultado[artista]["obras_con_precio"] += 1
                    total_rellenados += 1
                    logging.info("  ✅ %s – %s: %.0f€", artista, titulo, precio_num)
                time.sleep(0.5)

    with open("ventas_totales.json", "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    github_guardar_archivo("ventas_totales.json")
    logging.info("✅ ventas_totales.json actualizado. Precios rellenados: %d", total_rellenados)


def calcular_ventas_totales() -> None:
    """Visita cada obra vendida de cada artista y calcula el total vendido por artista."""
    logging.info("📊 Calculando ventas totales por artista...")
    resultado = {}

    for nombre_artista, datos in estado.items():
        if nombre_artista == "_meta":
            continue
        obras = datos.get("obras", {})
        vendidas = [(titulo, info["url"]) for titulo, info in obras.items() if info["estado"] == "vendido"]

        if not vendidas:
            continue

        logging.info("  [%s] %d obras vendidas — obteniendo precios...", nombre_artista, len(vendidas))
        total = 0.0
        detalle = []

        for titulo, url in vendidas:
            _, precio_num = obtener_precio_desde_producto(url)
            if precio_num > 0:
                total += precio_num
                detalle.append({"titulo": titulo, "precio_num": precio_num})
            time.sleep(0.5)

        resultado[nombre_artista] = {
            "total": total,
            "obras_vendidas": len(vendidas),
            "obras_con_precio": len(detalle),
            "detalle": detalle,
            "ultima_actualizacion": datetime.now().strftime("%d/%m/%Y %H:%M")
        }
        logging.info("  [%s] Total: %.0f€", nombre_artista, total)

    with open("ventas_totales.json", "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    github_guardar_archivo("ventas_totales.json")
    logging.info("✅ ventas_totales.json guardado en GitHub.")


def actualizar_ventas_totales(cambios: list) -> None:
    """Añade las nuevas ventas detectadas al ventas_totales.json."""
    if not os.path.exists("ventas_totales.json"):
        return
    try:
        with open("ventas_totales.json", "r", encoding="utf-8") as f:
            resultado = json.load(f)

        actualizados = 0
        for cambio in cambios:
            artista = cambio["artista"]["nombre"]
            for c in cambio.get("cambios_obras", []):
                if c["tipo"] in ("vendida", "nueva_vendida") and c.get("precio_num", 0) > 0:
                    if artista not in resultado:
                        resultado[artista] = {"total": 0.0, "obras_vendidas": 0, "obras_con_precio": 0, "detalle": [], "ultima_actualizacion": datetime.now().strftime("%d/%m/%Y %H:%M")}
                    resultado[artista]["detalle"].append({
                        "titulo": c["titulo"],
                        "precio_num": c["precio_num"]
                    })
                    resultado[artista]["obras_vendidas"] += 1
                    resultado[artista]["total"] += c["precio_num"]
                    resultado[artista]["obras_con_precio"] += 1
                    resultado[artista]["ultima_actualizacion"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                    actualizados += 1

        if actualizados > 0:
            with open("ventas_totales.json", "w", encoding="utf-8") as f:
                json.dump(resultado, f, ensure_ascii=False, indent=2)
            github_guardar_archivo("ventas_totales.json")
            logging.info("✅ ventas_totales.json actualizado con %d nuevas ventas.", actualizados)
    except Exception as e:
        logging.error("Error actualizando ventas_totales: %s", e)


def guardar_historial(cambios: list) -> None:
    """Acumula todos los cambios detectados en historial_cambios.json, sin sobreescribir."""
    try:
        if os.path.exists(ARCHIVO_HISTORIAL):
            with open(ARCHIVO_HISTORIAL, "r", encoding="utf-8") as f:
                historial = json.load(f)
        else:
            historial = []

        fecha_hora = datetime.now().strftime("%d/%m/%Y %H:%M")
        for cambio in cambios:
            for c in cambio.get("cambios_obras", []):
                historial.append({
                    "fecha":      fecha_hora,
                    "artista":    cambio["artista"]["nombre"],
                    "obra":       c["titulo"],
                    "tipo":       c["tipo"],
                    "precio":     c.get("precio", ""),
                    "precio_num": c.get("precio_num", 0.0),
                })

        with open(ARCHIVO_HISTORIAL, "w", encoding="utf-8") as f:
            json.dump(historial, f, ensure_ascii=False, indent=2)

        github_guardar_archivo(ARCHIVO_HISTORIAL)
        logging.info("Historial actualizado (%d registros totales).", len(historial))

    except Exception as e:
        logging.error("Error guardando historial: %s", e)


def enviar_resumen_mensual() -> None:
    """Envía el resumen del mes el último día del mes."""
    import calendar
    hoy = datetime.now()
    ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
    if hoy.day != ultimo_dia:
        return

    mes_actual = hoy.strftime("%Y-%m")
    nombre_mes = hoy.strftime("%B %Y").capitalize()

    try:
        if not os.path.exists(ARCHIVO_MENSUAL):
            logging.info("Sin datos mensuales para enviar.")
            return

        with open(ARCHIVO_MENSUAL, "r", encoding="utf-8") as f:
            acumulado = json.load(f)

        ventas = acumulado.get(mes_actual, [])
        if not ventas:
            asunto = f"📊 Artevistas — {nombre_mes} sin ventas registradas"
            cuerpo = f"""
            <html><body style="font-family:Arial,sans-serif;max-width:700px;margin:auto;padding:24px;">
              <h2 style="border-bottom:2px solid #2980b9;padding-bottom:10px;">
                📊 Resumen mensual — {nombre_mes}
              </h2>
              <p style="color:#888;">No se registraron ventas este mes.</p>
            </body></html>"""
        else:
            from collections import Counter
            total = sum(v["precio_num"] for v in ventas)
            num_obras = len(ventas)
            conteo = Counter(v["artista"] for v in ventas)
            importes = {}
            for v in ventas:
                importes[v["artista"]] = importes.get(v["artista"], 0) + v["precio_num"]
            top = sorted(conteo.items(), key=lambda x: importes[x[0]], reverse=True)[:5]

            filas_top = ""
            for artista, num in top:
                filas_top += f"""
                <tr>
                  <td style="padding:8px;border-bottom:1px solid #eee;">{artista}</td>
                  <td style="padding:8px;border-bottom:1px solid #eee;text-align:center;">{num}</td>
                  <td style="padding:8px;border-bottom:1px solid #eee;font-weight:bold;">{importes[artista]:,.0f} €</td>
                </tr>"""

            filas_detalle = ""
            for v in ventas:
                icono = "🔴" if v["tipo"] == "vendida" else "🟠"
                filas_detalle += f"""
                <tr>
                  <td style="padding:7px;border-bottom:1px solid #eee;font-size:13px;">{v["fecha"]}</td>
                  <td style="padding:7px;border-bottom:1px solid #eee;font-size:13px;">{v["artista"]}</td>
                  <td style="padding:7px;border-bottom:1px solid #eee;font-size:13px;">{icono} {v["obra"]}</td>
                  <td style="padding:7px;border-bottom:1px solid #eee;font-size:13px;font-weight:bold;">{v["precio"]}</td>
                </tr>"""

            asunto = f"📊 Artevistas — Resumen {nombre_mes}"
            cuerpo = f"""
            <html><body style="font-family:Arial,sans-serif;max-width:700px;margin:auto;padding:24px;">
              <h2 style="border-bottom:2px solid #2980b9;padding-bottom:10px;">
                📊 Resumen mensual — {nombre_mes}
              </h2>
              <div style="background:#1a1a2e;color:white;border-radius:10px;
                          padding:20px;margin-bottom:24px;text-align:center;">
                <p style="margin:0;font-size:14px;opacity:0.8;">Total vendido en {nombre_mes}</p>
                <p style="margin:8px 0;font-size:40px;font-weight:bold;">{total:,.0f} €</p>
                <p style="margin:0;font-size:14px;opacity:0.8;">
                  {num_obras} obra{"s" if num_obras > 1 else ""} vendida{"s" if num_obras > 1 else ""}
                </p>
              </div>
              <h3 style="color:#1a1a2e;">🏆 Top artistas del mes</h3>
              <table style="width:100%;border-collapse:collapse;margin-bottom:24px;font-size:14px;">
                <thead>
                  <tr style="background:#f4f4f4;">
                    <th style="padding:8px;text-align:left;">Artista</th>
                    <th style="padding:8px;text-align:center;">Obras</th>
                    <th style="padding:8px;text-align:left;">Importe</th>
                  </tr>
                </thead>
                <tbody>{filas_top}</tbody>
              </table>
              <h3 style="color:#1a1a2e;">📋 Detalle completo</h3>
              <table style="width:100%;border-collapse:collapse;font-size:13px;">
                <thead>
                  <tr style="background:#f4f4f4;">
                    <th style="padding:8px;text-align:left;">Fecha</th>
                    <th style="padding:8px;text-align:left;">Artista</th>
                    <th style="padding:8px;text-align:left;">Obra</th>
                    <th style="padding:8px;text-align:left;">Precio</th>
                  </tr>
                </thead>
                <tbody>{filas_detalle}</tbody>
              </table>
              <br><small style="color:#aaa;">Monitor Artevistas · {hoy.strftime("%d/%m/%Y")}</small>
            </body></html>"""

        enviar_email(asunto, cuerpo)
        logging.info("Resumen mensual enviado (%s).", nombre_mes)

    except Exception as e:
        logging.error("Error enviando resumen mensual: %s", e)



def migrar_estado_a_url_clave() -> None:
    """Migra el estado antiguo (clave=titulo) al nuevo formato (clave=url)."""
    global estado
    migrado = 0
    for nombre, datos in estado.items():
        if nombre == "_meta":
            continue
        obras = datos.get("obras", {})
        obras_nuevas = {}
        necesita_migracion = False
        for clave, info in obras.items():
            # Si la clave es una URL ya está migrado
            if clave.startswith("http"):
                obras_nuevas[clave] = info
            else:
                # Clave es título — migrar a URL
                necesita_migracion = True
                url = info.get("url") or clave
                if "titulo" not in info:
                    info["titulo"] = clave
                obras_nuevas[url] = info
        if necesita_migracion:
            datos["obras"] = obras_nuevas
            migrado += 1
    if migrado > 0:
        logging.info("Estado migrado a clave URL: %d artistas actualizados.", migrado)




def comprobar_todos() -> None:
    global cambios_del_dia
    logging.info("─" * 50)

    # Detectar artistas nuevos/desaparecidos
    cambios_artistas = detectar_artistas_nuevos()
    if cambios_artistas:
        for c in cambios_artistas:
            tipo = c["tipo"]
            nombre = c["artista"]["nombre"]
            if tipo == "nuevo_artista":
                cambios_del_dia.append({
                    "artista": c["artista"],
                    "diff": "",
                    "cambios_obras": [{"tipo": "nuevo_artista", "titulo": nombre, "precio": "", "precio_num": 0}],
                    "hora": datetime.now().strftime("%H:%M"),
                })
            elif tipo == "artista_desaparecido":
                cambios_del_dia.append({
                    "artista": c["artista"],
                    "diff": "",
                    "cambios_obras": [{"tipo": "artista_desaparecido", "titulo": nombre, "precio": "", "precio_num": 0}],
                    "hora": datetime.now().strftime("%H:%M"),
                })

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
    if cambios_del_dia:
        guardar_ventas_mensuales(cambios_del_dia)
        guardar_historial(cambios_del_dia)
        actualizar_ventas_totales(cambios_del_dia)
    logging.info("Comprobación finalizada. Cambios acumulados hoy: %d", len(cambios_del_dia))
    cambios_del_dia = []


# ── Diagnóstico HTML ──────────────────────────

def diagnosticar_html() -> None:
    """Imprime en los logs qué selectores funcionan en Artevistas. Se ejecuta una sola vez al arrancar."""
    artista_test = ARTISTAS[1]  # Akore
    logging.info("🔍 DIAGNÓSTICO HTML — probando con: %s", artista_test["url"])

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "es-ES,es;q=0.9",
    }
    try:
        resp = requests.get(artista_test["url"], headers=headers, timeout=20)
        logging.info("🔍 Status HTTP: %d", resp.status_code)
        soup = BeautifulSoup(resp.text, "html.parser")

        selectores = [
            "li.product",
            "ul.products li",
            "article.product",
            ".wc-block-grid__product",
            ".product-item",
            ".products .type-product",
        ]
        for sel in selectores:
            n = len(soup.select(sel))
            logging.info("🔍 Selector %-45s -> %d elementos", repr(sel), n)

        # Clases con 'product'
        clases = set()
        for tag in soup.find_all(True):
            for cls in tag.get("class", []):
                if "product" in cls.lower():
                    clases.add(f"{tag.name}.{cls}")
        logging.info("🔍 Clases con 'product': %s", ", ".join(sorted(clases)[:20]))

        # Primer bloque de producto en crudo
        primer = soup.select_one("li.product") or soup.select_one("article.product")
        if not primer:
            for tag in soup.find_all(["li", "article", "div"]):
                if any("product" in c.lower() for c in tag.get("class", [])):
                    primer = tag
                    break
        if primer:
            html_crudo = primer.prettify()[:800]
            logging.info("🔍 HTML primer producto:\n%s", html_crudo)
        else:
            logging.warning("🔍 No se encontro ningun bloque de producto")

        # Paginacion
        sig = soup.select_one("a.next.page-numbers, .woocommerce-pagination a.next")
        logging.info("🔍 Paginacion siguiente: %s", sig["href"] if sig else "No encontrada")

    except Exception as e:
        logging.error("🔍 Error en diagnostico: %s", e)


ARCHIVO_ARTISTAS = "artistas_artevistas.json"


def obtener_artistas_web() -> list:
    """Scraping de la página de artistas de Artevistas para obtener lista actualizada."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "es-ES,es;q=0.9",
        }
        r = requests.get("https://www.artevistas.eu/artist/", headers=headers, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        artistas = []
        for a in soup.select("a[href*='/artist/']"):
            href = a.get("href", "")
            nombre = a.get_text(strip=True)
            if not href or not nombre:
                continue
            if not href.startswith("http"):
                href = "https://www.artevistas.eu" + href
            if not href.endswith("/"):
                href += "/"
            # Filtrar la página de lista de artistas y enlaces genéricos
            if href.rstrip("/").endswith("/artist"):
                continue
            if len(nombre) < 2:
                continue
            artistas.append({"nombre": nombre, "url": href})
        # Deduplicar por URL
        vistos = set()
        unicos = []
        for a in artistas:
            if a["url"] not in vistos:
                vistos.add(a["url"])
                unicos.append(a)
        return unicos
    except Exception as e:
        logging.error("Error obteniendo artistas de la web: %s", e)
        return []


def detectar_artistas_nuevos() -> list:
    """Compara artistas de la web con los vigilados y detecta nuevos/desaparecidos."""
    global ARTISTAS

    artistas_web = obtener_artistas_web()
    if not artistas_web:
        return []

    urls_actuales = {a["url"] for a in ARTISTAS}
    urls_web = {a["url"] for a in artistas_web}

    nuevos = [a for a in artistas_web if a["url"] not in urls_actuales]
    desaparecidos = [a for a in ARTISTAS if a["url"] not in urls_web]

    cambios = []

    if nuevos:
        for a in nuevos:
            logging.info("🟢 Nuevo artista detectado: %s (%s)", a["nombre"], a["url"])
            ARTISTAS.append(a)
            cambios.append({"tipo": "nuevo_artista", "artista": a})

    if desaparecidos:
        for a in desaparecidos:
            # Verificar que realmente no existe (puede ser un problema de scraping)
            try:
                r = requests.head(a["url"], timeout=10)
                if r.status_code == 404:
                    logging.info("🔴 Artista desaparecido (404 confirmado): %s", a["nombre"])
                    ARTISTAS = [x for x in ARTISTAS if x["url"] != a["url"]]
                    cambios.append({"tipo": "artista_desaparecido", "artista": a})
                else:
                    logging.info("⚠️  Artista no en lista web pero URL activa: %s", a["nombre"])
            except Exception:
                logging.info("⚠️  No se pudo verificar artista: %s", a["nombre"])

    if cambios:
        # Guardar lista actualizada en GitHub
        try:
            with open(ARCHIVO_ARTISTAS, "w", encoding="utf-8") as f:
                json.dump(ARTISTAS, f, ensure_ascii=False, indent=2)
            github_guardar_archivo(ARCHIVO_ARTISTAS)
        except Exception as e:
            logging.error("Error guardando lista de artistas: %s", e)

    return cambios


def cargar_artistas_github() -> None:
    """Carga la lista de artistas desde GitHub si existe."""
    global ARTISTAS
    if not GITHUB_TOKEN:
        return
    try:
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }
        url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{ARCHIVO_ARTISTAS}"
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            import base64
            contenido = base64.b64decode(r.json()["content"]).decode("utf-8")
            ARTISTAS = json.loads(contenido)
            logging.info("Lista de artistas cargada desde GitHub: %d artistas.", len(ARTISTAS))
    except Exception as e:
        logging.warning("No se pudo cargar lista de artistas desde GitHub: %s", e)


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

    diagnosticar_html()  # <- diagnostico una sola vez al arrancar
    cargar_artistas_github()
    cargar_estado()
    migrar_estado_a_url_clave()
    comprobar_todos()

    # Calcular ventas totales si se activa con variable de entorno CALCULAR_VENTAS=1
    if os.environ.get("CALCULAR_VENTAS") == "1":
        calcular_ventas_totales()

    # Buscar obras faltantes en ventas_totales si se activa con BUSCAR_FALTANTES=1
    if os.environ.get("BUSCAR_FALTANTES") == "1":
        buscar_obras_faltantes()

    # Buscar duplicados por URL si se activa con BUSCAR_DUPLICADOS=1
    if os.environ.get("BUSCAR_DUPLICADOS") == "1":
        buscar_duplicados()

    # Rellenar precios faltantes si se activa con RELLENAR_PRECIOS=1
    if os.environ.get("RELLENAR_PRECIOS") == "1":
        rellenar_precios_faltantes()

    # Emails desactivados — usar webapp para ver cambios
    # enviar_resumen_diario()

    schedule.every().day.at("17:50").do(comprobar_todos)
    # schedule.every().day.at(HORA_ENVIO).do(enviar_resumen_diario)
    # schedule.every().day.at(HORA_ENVIO).do(enviar_resumen_mensual)

    logging.info("Scheduler activo. Próximo email a las 20:00 UTC (22:00 España).")

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
