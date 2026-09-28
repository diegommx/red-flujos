"""Capa analítica.

Produce las tablas que alimentan el dashboard y las señales de red:
- métricas de nodo (recibe/envía, PageRank, intermediación)
- ciclos cortos (simple_cycles; escala ok para <=15 orígenes)
- flujos entre actores monitoreados (de primera clase)
- desglose entrada/salida por canal por actor (alimenta el Sankey de canal)
- estructura compartida: vinculados-hub y pares de empresas con vínculo común
"""
from __future__ import annotations

import networkx as nx
import pandas as pd

def resumen_nodos(G_col: nx.DiGraph) -> pd.DataFrame:
    filas = []
    for n in G_col.nodes():
        rec = sum(d["total"] for _, _, d in G_col.in_edges(n, data=True))
        env = sum(d["total"] for _, _, d in G_col.out_edges(n, data=True))
        ntx = sum(d["n_tx"] for _, _, d in G_col.in_edges(n, data=True)) + sum(
            d["n_tx"] for _, _, d in G_col.out_edges(n, data=True)
        )
        filas.append(
            {
                "nit": n,
                "nombre": G_col.nodes[n].get("nombre", n),
                "tipo": G_col.nodes[n].get("tipo"),
                "tipo_persona": G_col.nodes[n].get("tipo_persona"),
                "recibido": rec,
                "enviado": env,
                "monto_total": rec + env,
                "n_tx": ntx,
            }
        )
    columnas = ["nit", "nombre", "tipo", "tipo_persona", "recibido", "enviado", "monto_total", "n_tx"]
    return pd.DataFrame(filas, columns=columnas).sort_values("monto_total", ascending=False).reset_index(drop=True)


def metricas_centralidad(G_p: nx.DiGraph) -> pd.DataFrame:
    pr = nx.pagerank(G_p, weight="total") if G_p.number_of_edges() else {}
    # En NetworkX un peso de betweenness significa DISTANCIA, no intensidad.
    # El número de saltos es la semántica segura por defecto para este grafo.
    btw = nx.betweenness_centrality(G_p, weight=None, normalized=True) if G_p.number_of_nodes() > 2 else {}
    filas = [
        {
            "nit": n,
            "nombre": G_p.nodes[n].get("nombre", n),
            "tipo": G_p.nodes[n].get("tipo"),
            "pagerank": pr.get(n, 0.0),
            "betweenness": btw.get(n, 0.0),
        }
        for n in G_p.nodes()
    ]
    return pd.DataFrame(filas, columns=["nit", "nombre", "tipo", "pagerank", "betweenness"]).sort_values(
        "pagerank", ascending=False).reset_index(drop=True)


def ciclos_cortos(
    G_p: nx.DiGraph, min_len: int = 2, max_len: int = 5, max_ciclos: int = 500
) -> list[list[str]]:
    """Ciclos de longitud acotada.

    Se usa ``length_bound`` para evitar la explosión de ``simple_cycles`` cuando
    el subgrafo entre actores monitoreados es muy denso, y se limita el número
    total devuelto por seguridad.
    """
    out: list[list[str]] = []
    for c in nx.simple_cycles(G_p, length_bound=max_len):
        if len(c) >= min_len:
            out.append(c)
        if len(out) >= max_ciclos:
            break
    return sorted(out, key=len)


def flujos_entre_actores(G_col: nx.DiGraph, nits_conocidos: set[str]) -> pd.DataFrame:
    """Aristas de flujo entre actores monitoreados (matriz origen->destino).

    'mismo_actor' marca los casos donde origen == destino. Se conservan,
    separados de las relaciones entre entidades distintas.
    """
    filas = []
    for u, v, d in G_col.edges(data=True):
        if u in nits_conocidos and v in nits_conocidos:
            filas.append(
                {
                    "origen": u,
                    "origen_nombre": G_col.nodes[u].get("nombre", u),
                    "destino": v,
                    "destino_nombre": G_col.nodes[v].get("nombre", v),
                    "mismo_actor": u == v,
                    "total": d["total"],
                    "n_tx": d["n_tx"],
                }
            )
    df = pd.DataFrame(filas)
    return df.sort_values("total", ascending=False).reset_index(drop=True) if len(df) else df


def canal_por_actor(df_aristas_canal: pd.DataFrame, nits_conocidos: set[str]) -> pd.DataFrame:
    """Entrada/salida por canal para cada actor monitoreado.

    Salida (sale): el actor es 'origen'.  Entrada (entra): es 'destino'.
    Esta tabla alimenta directamente el Sankey de canal por actor.
    """
    sale = df_aristas_canal[df_aristas_canal["origen"].isin(nits_conocidos)].copy()
    sale = sale.rename(columns={"origen": "actor"})[["actor", "canal", "total", "n_tx"]]
    sale["sentido"] = "SALE"
    entra = df_aristas_canal[df_aristas_canal["destino"].isin(nits_conocidos)].copy()
    entra = entra.rename(columns={"destino": "actor"})[["actor", "canal", "total", "n_tx"]]
    entra["sentido"] = "ENTRA"
    res = pd.concat([sale, entra], ignore_index=True)
    return (
        res.groupby(["actor", "sentido", "canal"], as_index=False)
        .agg(total=("total", "sum"), n_tx=("n_tx", "sum"))
        .sort_values(["actor", "sentido", "total"], ascending=[True, True, False])
        .reset_index(drop=True)
    )


def canal_modalidad_actor(df: pd.DataFrame, nits_conocidos: set[str]) -> pd.DataFrame:
    """Entrada/salida por (canal, modalidad NombreTX) para cada actor.

    Alimenta el Sankey de tres niveles:
        modalidad → canal → ACTOR → canal → modalidad
    Trabaja directo sobre el df transaccional filtrado (tiene origen/destino/
    canal/nombre_tx/valor por fila).
    """
    d = df.copy()
    d["nombre_tx"] = d["nombre_tx"].fillna("").astype(str).str.strip()
    d.loc[d["nombre_tx"] == "", "nombre_tx"] = "(sin detalle)"

    sale = d[d["origen"].isin(nits_conocidos)].rename(columns={"origen": "actor"})
    sale = sale.groupby(["actor", "canal", "nombre_tx"], as_index=False).agg(
        total=("valor", "sum"), n_tx=("valor", "size")
    )
    sale["sentido"] = "SALE"

    entra = d[d["destino"].isin(nits_conocidos)].rename(columns={"destino": "actor"})
    entra = entra.groupby(["actor", "canal", "nombre_tx"], as_index=False).agg(
        total=("valor", "sum"), n_tx=("valor", "size")
    )
    entra["sentido"] = "ENTRA"

    return (
        pd.concat([sale, entra], ignore_index=True)
        .sort_values(["actor", "sentido", "total"], ascending=[True, True, False])
        .reset_index(drop=True)
    )


def estructura_compartida(df_vin: pd.DataFrame, umbral_hub: int = 3):
    """Devuelve (hubs, pares).

    hubs  : vinculados ligados a >= umbral_hub empresas (bandera roja).
    pares : pares de empresas que comparten un mismo vinculado + relación.
    """
    g = (
        df_vin.groupby(["nit_vinculado", "nombre_vinculado"])
        .agg(
            n_empresas=("nit_empresa", "nunique"),
            empresas=("nit_empresa", lambda s: sorted(set(s))),
            relaciones=("relacion", lambda s: sorted(set(s))),
        )
        .reset_index()
        .sort_values("n_empresas", ascending=False)
    )
    hubs = g[g["n_empresas"] >= umbral_hub].reset_index(drop=True)

    filas = []
    for (vin, rel), grp in df_vin.groupby(["nit_vinculado", "relacion"]):
        emps = sorted(set(grp["nit_empresa"]))
        if len(emps) < 2:
            continue
        nom = grp["nombre_vinculado"].iloc[0]
        for i in range(len(emps)):
            for j in range(i + 1, len(emps)):
                filas.append(
                    {
                        "empresa_a": emps[i],
                        "empresa_b": emps[j],
                        "vinculado": vin,
                        "nombre_vinculado": nom,
                        "relacion": rel,
                    }
                )
    pares = pd.DataFrame(filas)
    return hubs, pares
