"""Layout adaptativo multi-columna para el grafo de flujos.

Reemplaza la rejilla fija del notebook. Distribuye:

    [ EMISORES ]  ->  [ ACTORES MONITOREADOS ]  ->  [ RECEPTORES ]

- El número de columnas de ACTORES se adapta al conteo (1 columna hasta
  ``max_por_columna``; 2 columnas si hay más — pensado para <=15 orígenes).
- La cola larga de contrapartes (emisores/receptores) se colapsa en nodos
  "Otros (N)" por lado, agregando sus montos hacia/desde los actores. Así el
  grafo no se satura aunque haya cientos de contrapartes.
- La clasificación emisor/receptor es por flujo NETO respecto a los actores,
  para evitar una columna intermedia confusa de nodos "mixtos".
- 'SIN_CONTRAPARTE' se ubica aparte, a la derecha.
"""
from __future__ import annotations

import math

import networkx as nx

from ..normalize import NIT_DESCONOCIDO, es_desconocido


def _monto(G: nx.DiGraph, n) -> float:
    e = sum(d["total"] for _, _, d in G.out_edges(n, data=True))
    r = sum(d["total"] for _, _, d in G.in_edges(n, data=True))
    return e + r


def _flujo_con_actores(G, n, nits):
    """(total que envía a actores, total que recibe de actores)."""
    t_out = sum(d["total"] for _, v, d in G.out_edges(n, data=True) if v in nits)
    t_in = sum(d["total"] for u, _, d in G.in_edges(n, data=True) if u in nits)
    return t_out, t_in


def preparar_visual(G_col, nits_conocidos, top_por_lado=12, max_por_columna=8,
                    mostrar_otros: bool = True):
    """Devuelve (G_vis, pos, meta).

    G_vis : grafo con la cola larga colapsada en nodos 'Otros' (o descartada
            si ``mostrar_otros=False``).
    pos   : {nodo: (x, y)} para el render.
    meta  : conteos para mostrar en la UI.
    """
    nits = set(nits_conocidos)
    actores = [n for n in G_col.nodes() if n in nits]
    externos = [n for n in G_col.nodes() if n not in nits and not es_desconocido(n)]

    # Clasificar externos por flujo NETO con los actores
    emisores, receptores = [], []
    for n in externos:
        t_out, t_in = _flujo_con_actores(G_col, n, nits)
        (emisores if t_out >= t_in else receptores).append(n)

    def top_cola(nodos):
        ordenados = sorted(nodos, key=lambda n: _monto(G_col, n), reverse=True)
        return ordenados[:top_por_lado], ordenados[top_por_lado:]

    top_emi, cola_emi = top_cola(emisores)
    top_rec, cola_rec = top_cola(receptores)

    conservar = (set(actores) | set(top_emi) | set(top_rec)) & set(G_col.nodes())
    G_vis = G_col.subgraph(conservar).copy()

    # Los extremos desconocidos son independientes en el motor. Sólo la vista
    # los resume en un nodo virtual, sin usarlo para métricas de topología.
    desconocidos = [n for n in G_col if es_desconocido(n)]
    if desconocidos:
        G_vis.add_node(NIT_DESCONOCIDO, nombre="Sin contraparte", tipo="desconocido")
        resumen_desconocido: dict[tuple[str, str], tuple[float, int]] = {}
        for n in desconocidos:
            for u, v, dat in list(G_col.in_edges(n, data=True)) + list(G_col.out_edges(n, data=True)):
                a, b = (NIT_DESCONOCIDO if u == n else u), (NIT_DESCONOCIDO if v == n else v)
                if a not in nits and b not in nits:
                    continue
                total, cuenta = resumen_desconocido.get((a, b), (0.0, 0))
                resumen_desconocido[(a, b)] = (total + dat["total"], cuenta + dat["n_tx"])
        for (a, b), (total, cuenta) in resumen_desconocido.items():
            G_vis.add_edge(a, b, total=total, n_tx=cuenta, por_canal={})

    def agregar_otros(cola, nombre_id, hacia_actor: bool):
        if not cola:
            return None
        acc: dict = {}
        for n in cola:
            if hacia_actor:  # cola -> actor
                for _, v, d in G_col.out_edges(n, data=True):
                    if v in nits:
                        t, c = acc.get(v, (0, 0))
                        acc[v] = (t + d["total"], c + d["n_tx"])
            else:            # actor -> cola
                for u, _, d in G_col.in_edges(n, data=True):
                    if u in nits:
                        t, c = acc.get(u, (0, 0))
                        acc[u] = (t + d["total"], c + d["n_tx"])
        if not acc:
            return None
        G_vis.add_node(nombre_id, nombre=f"Otros ({len(cola)})", tipo="otros", tipo_persona="ND")
        for actor, (t, c) in acc.items():
            if hacia_actor:
                G_vis.add_edge(nombre_id, actor, total=t, n_tx=c, por_canal={})
            else:
                G_vis.add_edge(actor, nombre_id, total=t, n_tx=c, por_canal={})
        return nombre_id

    if mostrar_otros:
        otros_emi = agregar_otros(cola_emi, "OTROS_EMISORES", hacia_actor=True)
        otros_rec = agregar_otros(cola_rec, "OTROS_RECEPTORES", hacia_actor=False)
    else:
        otros_emi = otros_rec = None

    # ---- posiciones -------------------------------------------------------
    n_col_actores = 1 if len(actores) <= max_por_columna else 2
    x_emisores = 0.0
    x_receptores = 3.0
    # columnas de actores repartidas entre 1.0 y 2.0
    if n_col_actores == 1:
        xs_actores = [1.5]
    else:
        xs_actores = [1.15, 1.85]

    pos: dict = {}

    def colocar(nodos, x):
        m = len(nodos)
        if m == 0:
            return
        nodos = sorted(nodos, key=lambda n: _monto(G_vis, n), reverse=True)
        for i, n in enumerate(nodos):
            y = (i - (m - 1) / 2.0)  # centrado vertical
            pos[n] = (x, y)

    # emisores (incluye Otros)
    col_emi = list(top_emi) + ([otros_emi] if otros_emi else [])
    colocar(col_emi, x_emisores)

    # actores repartidos en columnas
    actores_ord = sorted(actores, key=lambda n: _monto(G_vis, n), reverse=True)
    for idx, x in enumerate(xs_actores):
        sub = actores_ord[idx::n_col_actores]
        colocar(sub, x)

    # receptores (incluye Otros) + SIN_CONTRAPARTE
    col_rec = list(top_rec) + ([otros_rec] if otros_rec else [])
    colocar(col_rec, x_receptores)
    if NIT_DESCONOCIDO in G_vis.nodes():
        # ubicar SIN_CONTRAPARTE debajo de la columna de receptores
        ys = [y for (_, y) in [pos[n] for n in col_rec]] if col_rec else [0]
        pos[NIT_DESCONOCIDO] = (x_receptores, (min(ys) - 1.5) if ys else 0)

    meta = {
        "n_actores": len(actores),
        "n_emisores_mostrados": len(top_emi),
        "n_emisores_colapsados": len(cola_emi),
        "n_receptores_mostrados": len(top_rec),
        "n_receptores_colapsados": len(cola_rec),
        "columnas_actores": n_col_actores,
        "nodos_visibles": G_vis.number_of_nodes(),
    }
    return G_vis, pos, meta
