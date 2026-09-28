"""Filtros dinámicos del dashboard.

Los filtros de la UI operan sobre el dataset YA cargado (subconjunto en
memoria), no vuelven a consultar SQL. El universo cargado lo define
``filtro_carga`` en config.yaml; estos filtros son una vista de ese universo.

La EXCLUSIÓN de nodos opera a nivel de datos: se descartan las transacciones
que tocan el nodo excluido, de modo que KPIs, grafo, Sankey y heatmaps quedan
coherentes entre sí (excluir = sacar del análisis, no solo esconder el dibujo).
"""
from __future__ import annotations

import pandas as pd

from ..graphs import construir_grafo_transaccional
from ..normalize import NIT_DESCONOCIDO, es_desconocido


def opciones(res, mapa_nombre: dict | None = None) -> dict:
    df = res.df_tx
    mapa = mapa_nombre or res.mapa_nombre
    actores = {nit: (mapa.get(nit) or nit) for nit in res.clientes}
    return {
        "fecha_min": df["fecha"].min().date(),
        "fecha_max": df["fecha"].max().date(),
        "monto_max": float(df["valor"].max()) if len(df) else 0.0,
        "canales": sorted(df["canal"].dropna().unique().tolist()),
        "actores": dict(sorted(actores.items(), key=lambda kv: kv[1])),
    }


def opciones_nodos_excluibles(res, mapa_nombre: dict | None = None, top: int = 300):
    """Candidatos a exclusión: actores + top-N contrapartes por monto + SIN_CONTRAPARTE.

    Devuelve (lista_de_nits_ordenada, {nit: etiqueta}).
    """
    mapa = mapa_nombre or res.mapa_nombre
    rn = res.resumen_nodos
    nits_top = [n for n in rn.head(top)["nit"].tolist() if not es_desconocido(n)]
    universo = list(dict.fromkeys(list(res.clientes) + nits_top))  # actores primero, sin duplicar
    if any(es_desconocido(n) for n in rn["nit"]) and NIT_DESCONOCIDO not in universo:
        universo.append(NIT_DESCONOCIDO)

    def etiqueta(nit: str) -> str:
        if nit == NIT_DESCONOCIDO:
            return "Sin contraparte"
        nom = mapa.get(nit) or ""
        return f"{nom} · {nit}" if nom and nom != nit else nit

    return universo, {n: etiqueta(n) for n in universo}


def aplicar(res, *, fecha_desde=None, fecha_hasta=None, monto_min=0.0,
            canales=None, sentido="TODOS", actores_foco=None,
            excluir_nodos=None) -> pd.DataFrame:
    df = res.df_tx
    m = pd.Series(True, index=df.index)
    if fecha_desde is not None:
        m &= df["fecha"].dt.date >= fecha_desde
    if fecha_hasta is not None:
        m &= df["fecha"].dt.date <= fecha_hasta
    if monto_min:
        m &= df["valor"] >= monto_min
    if canales:
        m &= df["canal"].isin(canales)
    if sentido == "SALIDAS":
        m &= df["sentido"] == "DEBITO"
    elif sentido == "ENTRADAS":
        m &= df["sentido"] == "CREDITO"
    if excluir_nodos:
        ex = set(excluir_nodos)
        ex_desconocido = NIT_DESCONOCIDO in ex
        m &= ~(df["origen"].isin(ex) | df["destino"].isin(ex))
        if ex_desconocido:
            m &= ~(df["origen"].map(es_desconocido) | df["destino"].map(es_desconocido))
    out = df[m].copy()
    if actores_foco:
        af = set(actores_foco)
        out = out[out["origen"].isin(af) | out["destino"].isin(af)].copy()
    return out


def reconstruir_grafo(res, df: pd.DataFrame, mapa_nombre: dict | None = None):
    """Rebuild del grafo colapsado + aristas por canal a partir del df filtrado.

    ``mapa_nombre`` permite inyectar alias definidos por el usuario (nodos
    renombrados) sin mutar el Resultado cacheado.
    """
    nits = set(res.clientes)
    mapa = mapa_nombre or res.mapa_nombre
    return construir_grafo_transaccional(df, nits, res.clientes, mapa)
