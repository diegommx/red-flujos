"""Redes interactivas (pyvis / vis-network) embebidas en Streamlit.

Sustituye al grafo Plotly estático. Ventajas que motivan el cambio:
- Nodos ARRASTRABLES (reorganización manual de la disposición).
- FLECHAS nativas que hacen evidente la dirección del flujo.
- Zoom/pan fluidos y tooltips por nodo y por arista.

El HTML se genera con recursos *inline* (sin CDN): funciona en entornos
corporativos sin salida a internet.

Nota: las posiciones movidas a mano viven en el navegador; al cambiar un
filtro se re-renderiza y vuelven al layout calculado (limitación conocida
del MVP, ver README).
"""
from __future__ import annotations

import math
import html

import networkx as nx

from . import palette as pal
from . import formatting as fmt

_ESCALA_X = 300   # px por unidad de columna del layout
_ESCALA_Y = 78    # px por unidad vertical del layout


def _tt(*lineas: str) -> str:
    """Tooltip multilínea para vis-network."""
    return "\n".join(html.escape(str(linea)) for linea in lineas)


def _etiqueta(nombre: str, nit: str, max_len: int = 24) -> str:
    """Etiqueta de nodo con nombre e identificación a la vez (dos líneas)."""
    nom = (nombre[:max_len] + "…") if len(nombre) > max_len + 1 else nombre
    if not nombre or nombre == nit:
        return nit
    return f"{nom}\n{nit}"


def red_transaccional_html(G_vis: nx.DiGraph, pos: dict, height: int = 640,
                           presentacion: dict | None = None) -> str:
    """Grafo de flujos: arrastrable, con flechas y grosor ~ cantidad."""
    from pyvis.network import Network

    net = Network(
        height=f"{height}px", width="100%", directed=True,
        bgcolor="#FFFFFF", font_color=pal.TEXTO, cdn_resources="in_line",
    )
    net.toggle_physics(False)  # respeta el layout por columnas; nodos quedan arrastrables

    montos = {
        n: (sum(d["total"] for _, _, d in G_vis.out_edges(n, data=True))
            + sum(d["total"] for _, _, d in G_vis.in_edges(n, data=True)))
        for n in G_vis.nodes()
    }
    mmax = max(montos.values()) if montos else 1.0
    tmax = max((d["total"] for _, _, d in G_vis.edges(data=True)), default=1.0)
    ids_html = {n: f"n{i}" for i, n in enumerate(G_vis.nodes())}

    for n in G_vis.nodes():
        dat = G_vis.nodes[n]
        tipo = dat.get("tipo", "externo")
        nombre = dat.get("nombre") or n
        env = sum(d["total"] for _, _, d in G_vis.out_edges(n, data=True))
        rec = sum(d["total"] for _, _, d in G_vis.in_edges(n, data=True))
        x, y = pos.get(n, (0, 0))
        es_agregado = str(n).startswith("OTROS_")
        net.add_node(
            ids_html[n],
            label=html.escape(str(nombre if es_agregado else _etiqueta(nombre, n))),
            x=x * _ESCALA_X, y=-y * _ESCALA_Y,
            size=13 + 30 * math.sqrt(montos[n] / mmax),
            color={"background": pal.NODO.get(tipo, pal.NODO["externo"]),
                   "border": pal.NODO_BORDE},
            borderWidth=2,
            font={"size": pal.RED_FONT_SIZE, "color": pal.TEXTO, "multi": True},
            title=_tt(nombre, f"{(presentacion or {}).get('identificador', 'ID')}: {n}",
                      f"Envía: {fmt.cantidad(env, presentacion)}", f"Recibe: {fmt.cantidad(rec, presentacion)}"),
        )

    for u, v, d in G_vis.edges(data=True):
        frac = math.sqrt(d["total"] / tmax) if tmax else 0
        net.add_edge(
            ids_html[u], ids_html[v],
            width=1 + 7 * frac,
            color=pal.ARISTA_NEUTRA,
            arrows="to",
            smooth={"type": "curvedCW", "roundness": 0.12},
            title=_tt(
                f"{G_vis.nodes[u].get('nombre', u)}  →  {G_vis.nodes[v].get('nombre', v)}",
                f"{fmt.cantidad(d['total'], presentacion)} · {d['n_tx']} eventos",
            ),
        )

    return net.generate_html(notebook=False)


def estructura_html(
    G_est: nx.MultiDiGraph,
    mapa_nombre: dict[str, str],
    nits_hub: set[str],
    height: int = 560,
    presentacion: dict | None = None,
) -> str:
    """Grafo de relaciones: entidades (cajas) ↔ relacionados (círculos), hubs en rojo.

    Usa física (resortes) para un layout orgánico: los vinculados compartidos
    quedan naturalmente al centro entre las empresas que conectan.
    """
    from pyvis.network import Network

    net = Network(
        height=f"{height}px", width="100%", directed=False,
        bgcolor="#FFFFFF", font_color=pal.TEXTO, cdn_resources="in_line",
    )
    net.barnes_hut(gravity=-2600, central_gravity=0.25, spring_length=170, damping=0.35)

    # grado de vinculado = a cuántas empresas se liga (para tamaño)
    grado_emp: dict[str, set] = {}
    for emp, vin in G_est.edges():
        grado_emp.setdefault(vin, set()).add(emp)
    ids_html = {n: f"n{i}" for i, n in enumerate(G_est.nodes())}

    for n, dat in G_est.nodes(data=True):
        if dat.get("clase") == "empresa":
            nombre = mapa_nombre.get(n) or n
            net.add_node(
                ids_html[n], label=html.escape(str(_etiqueta(nombre, n, max_len=22))),
                shape="box",
                color={"background": pal.ESTRUCTURA["empresa_fondo"],
                       "border": pal.ESTRUCTURA["empresa_borde"]},
                borderWidth=2,
                font={"size": pal.ESTRUCTURA_FONT_SIZE, "color": pal.TEXTO, "multi": True},
                title=_tt(nombre, f"{(presentacion or {}).get('identificador', 'ID')}: {n}",
                          f"Categoría: {dat.get('ciiu', '') or 'ND'}"),
            )
        else:
            nombre = dat.get("nombre") or mapa_nombre.get(n) or n
            es_hub = n in nits_hub
            n_emp = len(grado_emp.get(n, ()))
            net.add_node(
                ids_html[n], label=html.escape(str(_etiqueta(nombre, n, max_len=22))),
                shape="dot",
                size=14 + 5 * n_emp + (6 if es_hub else 0),
                color={"background": pal.ESTRUCTURA["hub_fondo"] if es_hub else pal.ESTRUCTURA["vinculado"],
                       "border": pal.ESTRUCTURA["hub_borde"] if es_hub else pal.ESTRUCTURA["vinculado_borde"]},
                borderWidth=2 + (1 if es_hub else 0),
                font={"size": pal.ESTRUCTURA_FONT_SIZE, "color": pal.TEXTO, "multi": True},
                title=_tt(nombre, f"ID: {n}",
                          f"Ligado a {n_emp} entidad(es)" + ("  ⚑ HUB" if es_hub else "")),
            )

    # combinar aristas paralelas (varios roles entre la misma pareja)
    combinadas: dict[tuple, list[str]] = {}
    for emp, vin, d in G_est.edges(data=True):
        combinadas.setdefault((emp, vin), []).append(d.get("relacion", ""))

    muchos = len(combinadas) > 40  # con muchas aristas, la etiqueta satura: solo tooltip
    for (emp, vin), roles in combinadas.items():
        etiqueta = " / ".join(sorted(set(r for r in roles if r)))
        net.add_edge(
            ids_html[emp], ids_html[vin],
            label=None if muchos else html.escape(etiqueta.title()[:34]),
            font={"size": pal.ESTRUCTURA_ARISTA_FONT, "color": pal.TEXTO_SUAVE, "align": "middle"},
            color=pal.ESTRUCTURA_ARISTA, width=1.5,
            title=_tt(etiqueta),
        )

    return net.generate_html(notebook=False)
