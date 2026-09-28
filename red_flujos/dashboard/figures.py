"""Figuras Plotly del dashboard: Sankey por actor y heatmaps entre actores.

(El grafo de red vive en ``network_html.py`` con pyvis: nodos arrastrables
y flechas de dirección, cosas que Plotly no ofrece.)
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from . import palette as pal
from . import formatting as fmt


# ---------------------------------------------------------------------------
# Sankey por actor:  modalidad → canal → ACTOR → canal → modalidad
# ---------------------------------------------------------------------------
def figura_sankey_actor(
    canal_mod: pd.DataFrame,
    actor: str,
    nombre: str,
    incluir_modalidad: bool = True,
    top_modalidades: int = 8,
    presentacion: dict | None = None,
) -> go.Figure:
    """Sankey de flujos del actor.

    - Nivel canal siempre presente (entrada a la izquierda, salida a la derecha).
    - Nivel modalidad (NombreTX) opcional en los extremos; las modalidades
      menores se agrupan en «Otras modalidades» para no saturar.
    - Colores de alto contraste: azul = entra, naranja = sale; el actor al
      centro en tono oscuro. Fuente 13px sobre fondo claro.
    """
    sub = canal_mod[canal_mod["actor"] == actor]
    if not len(sub):
        fig = go.Figure()
        fig.update_layout(title=f"Sin movimientos para {nombre} con los filtros actuales")
        return fig

    labels: list[str] = []
    colors: list[str] = []
    idx: dict[tuple, int] = {}

    def nodo(clave: tuple, label: str, color: str) -> int:
        if clave not in idx:
            idx[clave] = len(labels)
            labels.append(label)
            colors.append(color)
        return idx[clave]

    i_actor = nodo(("ACTOR",), nombre[:30], pal.SANKEY_NODO["actor"])
    src, tgt, val, lcol, ltxt = [], [], [], [], []

    def _preparar_lado(df_lado: pd.DataFrame, sentido: str):
        """Agrupa modalidades menores en 'Otras modalidades' (por lado)."""
        if not incluir_modalidad or not len(df_lado):
            return df_lado
        tot_mod = df_lado.groupby("nombre_tx")["total"].sum().sort_values(ascending=False)
        top = set(tot_mod.head(top_modalidades).index)
        d = df_lado.copy()
        d.loc[~d["nombre_tx"].isin(top), "nombre_tx"] = "Otras modalidades"
        return d.groupby(["canal", "nombre_tx"], as_index=False).agg(
            total=("total", "sum"), n_tx=("n_tx", "sum")
        )

    entra = _preparar_lado(sub[sub["sentido"] == "ENTRA"], "ENTRA")
    sale = _preparar_lado(sub[sub["sentido"] == "SALE"], "SALE")

    # --- lado ENTRADA: [modalidad] → canal → actor -------------------------
    ent_canal = entra.groupby("canal", as_index=False).agg(total=("total", "sum"), n_tx=("n_tx", "sum"))
    for _, r in ent_canal.iterrows():
        i_c = nodo(("IN_CH", r["canal"]), r["canal"], pal.SANKEY_NODO["canal_in"])
        src.append(i_c); tgt.append(i_actor); val.append(float(r["total"]))
        lcol.append(pal.ENTRADA_LINK)
        ltxt.append(f"Entra por {r['canal']}: {fmt.cantidad(r['total'], presentacion)} · {int(r['n_tx'])} eventos")
    if incluir_modalidad:
        for _, r in entra.iterrows():
            i_m = nodo(("IN_MOD", r["nombre_tx"]), r["nombre_tx"][:34], pal.SANKEY_NODO["mod_in"])
            i_c = idx[("IN_CH", r["canal"])]
            src.append(i_m); tgt.append(i_c); val.append(float(r["total"]))
            lcol.append(pal.ENTRADA_LINK)
            ltxt.append(f"{r['nombre_tx']} → {r['canal']}: {fmt.cantidad(r['total'], presentacion)} · {int(r['n_tx'])} eventos")

    # --- lado SALIDA: actor → canal → [modalidad] ---------------------------
    sal_canal = sale.groupby("canal", as_index=False).agg(total=("total", "sum"), n_tx=("n_tx", "sum"))
    for _, r in sal_canal.iterrows():
        i_c = nodo(("OUT_CH", r["canal"]), r["canal"], pal.SANKEY_NODO["canal_out"])
        src.append(i_actor); tgt.append(i_c); val.append(float(r["total"]))
        lcol.append(pal.SALIDA_LINK)
        ltxt.append(f"Sale por {r['canal']}: {fmt.cantidad(r['total'], presentacion)} · {int(r['n_tx'])} eventos")
    if incluir_modalidad:
        for _, r in sale.iterrows():
            i_m = nodo(("OUT_MOD", r["nombre_tx"]), r["nombre_tx"][:34], pal.SANKEY_NODO["mod_out"])
            i_c = idx[("OUT_CH", r["canal"])]
            src.append(i_c); tgt.append(i_m); val.append(float(r["total"]))
            lcol.append(pal.SALIDA_LINK)
            ltxt.append(f"{r['canal']} → {r['nombre_tx']}: {fmt.cantidad(r['total'], presentacion)} · {int(r['n_tx'])} eventos")

    fig = go.Figure(
        go.Sankey(
            arrangement="snap",
            node=dict(
                label=labels, color=colors, pad=18, thickness=18,
                line=dict(color="rgba(255,255,255,0.9)", width=1),
                hovertemplate="%{label}<extra></extra>",
            ),
            link=dict(
                source=src, target=tgt, value=val, color=lcol,
                customdata=ltxt, hovertemplate="%{customdata}<extra></extra>",
            ),
        )
    )
    fig.update_layout(
        font=dict(size=pal.SANKEY_FONT_SIZE, color=pal.SANKEY_FONT_COLOR, family="Arial"),
        height=560, margin=dict(l=10, r=10, t=30, b=15),
        paper_bgcolor="white",
    )
    return fig


# ---------------------------------------------------------------------------
# Heatmaps entre actores (monto y cantidad como vistas separadas)
# ---------------------------------------------------------------------------
def figura_heatmap_actores(flujos: pd.DataFrame, metrica: str = "total",
                           presentacion: dict | None = None) -> go.Figure:
    """Matriz origen×destino entre actores monitoreados.

    metrica = 'total' (cantidad en la unidad configurada) o 'n_tx' (# eventos,
    escala naranja) — dos vistas separadas para no mezclar unidades.
    """
    if flujos is None or len(flujos) == 0:
        fig = go.Figure()
        fig.update_layout(title="Sin flujos entre actores para los filtros actuales")
        return fig

    es_monto = metrica == "total"
    d = flujos.copy()
    # etiqueta de eje con nombre e identificación a la vez
    d["origen_lbl"] = d.apply(
        lambda r: f"{r['origen_nombre']}<br>{r['origen']}"
        if r["origen_nombre"] != r["origen"] else r["origen"], axis=1)
    d["destino_lbl"] = d.apply(
        lambda r: f"{r['destino_nombre']}<br>{r['destino']}"
        if r["destino_nombre"] != r["destino"] else r["destino"], axis=1)
    piv = d.pivot_table(
        index="origen_lbl", columns="destino_lbl", values=metrica,
        aggfunc="sum", fill_value=0,
    )
    escala = float((presentacion or {}).get("escala", 1) or 1)
    etiqueta_cantidad = (presentacion or {}).get("cantidad", "Cantidad")
    unidad = fmt.unidad_eje(presentacion)
    z = piv.values / escala if es_monto else piv.values
    fig = go.Figure(
        go.Heatmap(
            z=z, x=list(piv.columns), y=list(piv.index),
            colorscale="Blues" if es_monto else "Oranges",
            colorbar=dict(title=unidad if es_monto else "# eventos"),
            hovertemplate=(
                f"%{{y}} → %{{x}}<br>%{{z:,.1f}} {unidad}<extra></extra>"
                if es_monto else "%{y} → %{x}<br>%{z:,.0f} eventos<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        title=f"{etiqueta_cantidad} entre actores ({unidad})" if es_monto else "Cantidad de eventos entre actores",
        height=480, margin=dict(l=10, r=10, t=50, b=10),
        xaxis=dict(tickangle=-40, automargin=True, title="Destino"),
        yaxis=dict(automargin=True, title="Origen"),
        font=dict(size=12, color=pal.TEXTO),
    )
    return fig
