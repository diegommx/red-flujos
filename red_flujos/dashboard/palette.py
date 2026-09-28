"""Paleta y tipografía del dashboard — ÚNICO punto de personalización visual.

╔════════════════════════════════════════════════════════════════════════╗
║  GUÍA RÁPIDA: ¿qué constante cambia qué cosa?                           ║
╠════════════════════════════════════════════════════════════════════════╣
║  NODO[...]           → colores de los nodos en «Red de flujos»          ║
║  ENTRADA / SALIDA    → azul/naranja de entra-sale (Sankey, tablas)      ║
║  SANKEY_NODO[...]    → colores de nodos del Sankey «Canales por actor»  ║
║  SANKEY_FONT_SIZE    → tamaño de letra del Sankey                       ║
║  ESTRUCTURA[...]     → colores del grafo de relaciones                  ║
║  RED_FONT_SIZE /                                                        ║
║  ESTRUCTURA_FONT_SIZE→ tamaño de letra de los dos grafos de red         ║
║  TEXTO / TEXTO_SUAVE → color general del texto en figuras               ║
╚════════════════════════════════════════════════════════════════════════╝

Principios:
- Un solo significado por color en TODA la app (consistencia visual).
- Par entrada/salida = azul/naranja (distinguible con daltonismo rojo-verde).
- Texto oscuro sobre fondos claros (contraste alto y legible).
"""

# --- Texto (todas las figuras) ----------------------------------------------
TEXTO = "#1C2833"               # texto principal (casi negro)
TEXTO_SUAVE = "#5D6D7E"         # texto secundario (etiquetas de arista, notas)

# --- Nodos del grafo «Red de flujos» ----------------------------------------
NODO = {
    "cliente": "#2E6FB7",       # actor monitoreado (azul)
    "externo": "#95A0AB",       # contraparte externa (gris)
    "otros": "#B8860B",         # agregado de cola larga (ámbar oscuro)
    "desconocido": "#8E44AD",   # SIN_CONTRAPARTE (púrpura)
}
NODO_BORDE = "#FFFFFF"
RED_FONT_SIZE = 14              # tamaño de letra de las etiquetas de nodo

# --- Dirección del flujo (consistente en Sankey, aristas y tablas) ----------
ENTRADA = "#2E86C1"             # azul
SALIDA = "#E67E22"              # naranja
ENTRADA_LINK = "rgba(46, 134, 193, 0.45)"
SALIDA_LINK = "rgba(230, 126, 34, 0.45)"
ARISTA_NEUTRA = "rgba(110, 120, 135, 0.55)"

# --- Sankey «Canales por actor» ----------------------------------------------
# Los colores de nodo son de la BARRA; la etiqueta de texto se dibuja FUERA
# de la barra (en SANKEY_FONT_COLOR), por eso pueden ser oscuros sin afectar
# la legibilidad del texto.
SANKEY_NODO = {
    "actor": "#22313F",         # actor al centro (barra oscura)
    "canal_in": "#2E86C1",      # canal de entrada (azul)
    "canal_out": "#E67E22",     # canal de salida (naranja)
    "mod_in": "#85C1E9",        # modalidad de entrada (azul claro)
    "mod_out": "#F5B041",       # modalidad de salida (naranja claro)
}
SANKEY_FONT_SIZE = 14           # sube a 15-16 si necesitas letra más grande
SANKEY_FONT_COLOR = "#111111"   # texto de las etiquetas del Sankey

# --- Grafo de relaciones -----------------------------------------------------
# Las cajas de empresa son CLARAS con texto oscuro (mucho más legible que
# texto blanco sobre caja oscura). El borde lleva el color de identidad.
ESTRUCTURA = {
    "empresa_fondo": "#D6EAF8",     # fondo de la caja de empresa (azul claro)
    "empresa_borde": "#2E6FB7",     # borde de la caja de empresa
    "vinculado": "#A9DFBF",         # persona/entidad vinculada (verde claro)
    "vinculado_borde": "#16A085",
    "hub_fondo": "#F5B7B1",         # vinculado-hub (rojo claro, texto oscuro)
    "hub_borde": "#C0392B",
}
ESTRUCTURA_FONT_SIZE = 14
ESTRUCTURA_ARISTA = "rgba(110, 120, 135, 0.7)"
ESTRUCTURA_ARISTA_FONT = 11     # tamaño de la etiqueta de relación en la línea
