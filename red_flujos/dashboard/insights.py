"""Insights en texto plano — la versión dashboard de las impresiones del
notebook original (conteos y montos que dan una primera lectura del flujo
entre las partes, antes de entrar a los gráficos).

A diferencia de las impresiones de consola (fijas, se pierden al scrollear),
estas se recalculan sobre la vista filtrada actual: cambian con los filtros
igual que el resto del dashboard.

Todo aquí son agregaciones pandas simples sobre datos ya cargados (sin
centralidad ni ciclos, que son costosos) — así el resumen responde al
instante en cada cambio de filtro.
"""
from __future__ import annotations

import pandas as pd

from ..analytics import flujos_entre_actores, resumen_nodos
from ..normalize import es_desconocido
from . import formatting as fmt


def _pct(a: float, b: float) -> str:
    return f"{(a / b * 100 if b else 0):.0f}%"


def resumen_global(df: pd.DataFrame) -> dict:
    total = float(df["valor"].sum())
    deb = float(df.loc[df["sentido"] == "DEBITO", "valor"].sum())
    cre = float(df.loc[df["sentido"] == "CREDITO", "valor"].sum())
    n_sc = int((df["origen"].map(es_desconocido) | df["destino"].map(es_desconocido)).sum())
    return {
        "n_tx": len(df),
        "monto_total": total,
        "monto_debito": deb,
        "monto_credito": cre,
        "n_sin_contraparte": n_sc,
        "fecha_desde": df["fecha"].min().date() if len(df) else None,
        "fecha_hasta": df["fecha"].max().date() if len(df) else None,
    }


def top_por_tipo(G_col, tipo: str, n: int = 8, por: str = "monto_total") -> pd.DataFrame:
    """Top-N nodos de un tipo ('cliente' | 'externo' | 'desconocido'), por monto o por # tx."""
    rn = resumen_nodos(G_col)
    sub = rn[rn["tipo"] == tipo]
    campo = "monto_total" if por == "monto_total" else "n_tx"
    return sub.sort_values(campo, ascending=False).head(n)


def desglose_canal(df: pd.DataFrame, n: int = 8) -> pd.DataFrame:
    g = (
        df.groupby("canal", as_index=False)
        .agg(monto=("valor", "sum"), n_tx=("valor", "size"))
        .sort_values("monto", ascending=False)
    )
    return g.head(n)


def generar_bullets(df: pd.DataFrame, G_col, nits: set, nombre_fn,
                    presentacion: dict | None = None) -> list[str]:
    """Insights en texto, en el espíritu de las impresiones del notebook."""
    p = presentacion or {}
    def money(x):
        return fmt.cantidad(x, p)
    id_label = p.get("identificador", "ID")
    cantidad_label = p.get("cantidad", "Cantidad").lower()
    g = resumen_global(df)
    out = []

    if not g["n_tx"]:
        return ["No hay eventos para los filtros actuales."]

    out.append(
        f"**{g['n_tx']:,} eventos** por **{money(g['monto_total'])}** "
        f"entre **{g['fecha_desde']}** y **{g['fecha_hasta']}**."
    )
    out.append(
        f"De la {cantidad_label} total, **{_pct(g['monto_debito'], g['monto_total'])} son salidas** "
        f"({money(g['monto_debito'])}) y **{_pct(g['monto_credito'], g['monto_total'])} son entradas** "
        f"({money(g['monto_credito'])})."
    )
    if g["n_sin_contraparte"]:
        out.append(
            f"**{g['n_sin_contraparte']:,} eventos** ({_pct(g['n_sin_contraparte'], g['n_tx'])}) "
            f"no tienen contraparte identificada."
        )

    top_env = top_por_tipo(G_col, "cliente", n=1, por="monto_total")
    if len(top_env):
        top_env_ord = resumen_nodos(G_col)
        top_env_ord = top_env_ord[top_env_ord["tipo"] == "cliente"].sort_values("enviado", ascending=False)
        top_rec_ord = resumen_nodos(G_col)
        top_rec_ord = top_rec_ord[top_rec_ord["tipo"] == "cliente"].sort_values("recibido", ascending=False)
        if len(top_env_ord):
            r = top_env_ord.iloc[0]
            out.append(f"El actor que **más envía** es **{r['nombre']}** ({id_label} {r['nit']}): {money(r['enviado'])}.")
        if len(top_rec_ord):
            r = top_rec_ord.iloc[0]
            out.append(f"El actor que **más recibe** es **{r['nombre']}** ({id_label} {r['nit']}): {money(r['recibido'])}.")

    top_ext = top_por_tipo(G_col, "externo", n=1, por="monto_total")
    if len(top_ext):
        r = top_ext.iloc[0]
        out.append(
            f"La contraparte externa con mayor movimiento es **{r['nombre']}** ({id_label} {r['nit']}): "
            f"recibe {money(r['recibido'])} · envía {money(r['enviado'])}."
        )

    flujos = flujos_entre_actores(G_col, nits)
    reales = flujos[~flujos["mismo_actor"]] if len(flujos) else flujos
    if len(reales):
        top_valor = reales.sort_values("total", ascending=False).iloc[0]
        out.append(
            f"El **flujo más grande entre dos actores monitoreados** es "
            f"**{top_valor['origen_nombre']} → {top_valor['destino_nombre']}**: "
            f"{money(top_valor['total'])} en {int(top_valor['n_tx'])} eventos."
        )
        top_frec = reales.sort_values("n_tx", ascending=False).iloc[0]
        if top_frec["origen"] != top_valor["origen"] or top_frec["destino"] != top_valor["destino"]:
            out.append(
                f"El **par con más eventos** es "
                f"**{top_frec['origen_nombre']} → {top_frec['destino_nombre']}**: "
                f"{int(top_frec['n_tx'])} eventos por {money(top_frec['total'])}."
            )
    n_mismo = int(flujos["mismo_actor"].sum()) if len(flujos) else 0
    if n_mismo:
        out.append(f"Se detectaron **{n_mismo} auto-flujos** (origen y destino son la misma entidad).")

    canal = desglose_canal(df, n=1)
    if len(canal):
        r = canal.iloc[0]
        out.append(
            f"El canal más usado es **{r['canal']}**: {money(r['monto'])} en {int(r['n_tx']):,} eventos "
            f"({_pct(r['n_tx'], g['n_tx'])} de los eventos)."
        )

    return out
