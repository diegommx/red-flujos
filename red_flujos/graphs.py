"""Construcción de grafos de flujos y relaciones con IDs canónicos.

- Flujos: DiGraph colapsado (una arista por par origen->destino) con
  cantidad, nº de eventos y desglose por canal en cada arista. Además una
  tabla de aristas resueltas por canal (origen, destino, canal) que alimenta
  el Sankey de canal por actor.
- Relaciones: MultiDiGraph entidad -> relacionado, tipado por 'relacion'.
"""
from __future__ import annotations

import networkx as nx
import pandas as pd

from .normalize import NIT_DESCONOCIDO, es_desconocido
from .validation import LOG


def construir_grafo_transaccional(
    df_todas: pd.DataFrame,
    nits_conocidos: set[str],
    tipo_persona: dict[str, str],
    mapa_nombre: dict[str, str],
):
    """Devuelve (G_col, df_aristas_canal)."""
    nombre_por_nit = {k: (v or k) for k, v in mapa_nombre.items()}

    def _tipo(nit: str) -> str:
        if es_desconocido(nit):
            return "desconocido"
        return "cliente" if nit in nits_conocidos else "externo"

    # Aristas colapsadas con desglose por canal
    G_col = nx.DiGraph()
    for (o, d), grp in df_todas.groupby(["origen", "destino"]):
        por_canal = (
            grp.groupby("canal")
            .agg(total=("valor", "sum"), n_tx=("valor", "size"))
            .to_dict("index")
        )
        G_col.add_edge(
            o, d,
            total=float(grp["valor"].sum()),
            n_tx=int(len(grp)),
            por_canal={c: {"total": float(v["total"]), "n_tx": int(v["n_tx"])}
                       for c, v in por_canal.items()},
        )

    for nit in G_col.nodes():
        G_col.nodes[nit].update(
            nombre="Sin contraparte" if es_desconocido(nit) else nombre_por_nit.get(nit, nit),
            tipo=_tipo(nit),
            tipo_persona=tipo_persona.get(nit, "ND"),
        )

    df_aristas_canal = (
        df_todas.groupby(["origen", "destino", "canal"])
        .agg(total=("valor", "sum"), n_tx=("valor", "size"))
        .reset_index()
    )

    monto = sum(d["total"] for _, _, d in G_col.edges(data=True))
    LOG.info(
        "Grafo de flujos: %d nodos | %d aristas | cantidad total %s",
        G_col.number_of_nodes(), G_col.number_of_edges(), f"{monto:,.0f}",
    )
    return G_col, df_aristas_canal


def subgrafo_topologia(G_p: nx.DiGraph) -> nx.DiGraph:
    """Excluye extremos desconocidos independientes de centralidad y ciclos."""
    desconocidos = {n for n in G_p if es_desconocido(n)}
    return G_p.subgraph(set(G_p.nodes()) - desconocidos).copy() if desconocidos else G_p


def subgrafo_principal(G_col: nx.DiGraph, nits_conocidos: set[str], filtros: dict) -> nx.DiGraph:
    """Actores, extremos desconocidos y externos según filtros de cantidad."""
    montos = {}
    for n in G_col.nodes():
        e = sum(d["total"] for _, _, d in G_col.out_edges(n, data=True))
        r = sum(d["total"] for _, _, d in G_col.in_edges(n, data=True))
        montos[n] = e + r

    externos = sorted(
        (n for n, d in G_col.nodes(data=True) if d.get("tipo") == "externo"),
        key=lambda n: montos[n], reverse=True,
    )
    top_n = set(externos[: filtros.get("top_n_externos", 60)])
    por_monto = {n for n in externos if montos[n] >= filtros.get("monto_minimo", 0)}

    cand = set(nits_conocidos) | {n for n in G_col if es_desconocido(n)} | top_n | por_monto
    cand |= set(map(str, filtros.get("incluir_forzados", [])))
    excluidos = set(map(str, filtros.get("excluir_nits", [])))
    cand -= excluidos
    if NIT_DESCONOCIDO in excluidos:
        cand = {n for n in cand if not es_desconocido(n)}
    cand &= set(G_col.nodes())

    G_p = G_col.subgraph(cand).copy()
    LOG.info("Subgrafo principal: %d nodos | %d aristas", G_p.number_of_nodes(), G_p.number_of_edges())
    return G_p


def construir_grafo_estructural(df_vin: pd.DataFrame) -> nx.MultiDiGraph:
    """MultiDiGraph empresa -> vinculado, una arista por relación."""
    G = nx.MultiDiGraph()
    for _, r in df_vin.iterrows():
        emp, vin = r["nit_empresa"], r["nit_vinculado"]
        G.add_node(emp, clase="empresa", ciiu=r.get("codigo_ciiu", ""))
        if vin not in G.nodes or G.nodes[vin].get("clase") != "empresa":
            G.add_node(vin, clase="vinculado", nombre=r["nombre_vinculado"])
        G.add_edge(emp, vin, relacion=r["relacion"])
    LOG.info(
        "Grafo estructural: %d nodos | %d relaciones", G.number_of_nodes(), G.number_of_edges()
    )
    return G
