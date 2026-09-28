"""Dashboard local: solicita la fuente antes de cargar cualquier dato."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import streamlit as st

from red_flujos import Config, analizar
from red_flujos.demo import demo_config
from red_flujos.analytics import canal_modalidad_actor, flujos_entre_actores
from red_flujos.dashboard import aliases as als
from red_flujos.dashboard import figures as fig
from red_flujos.dashboard import filters as flt
from red_flujos.dashboard import formatting as fmt
from red_flujos.dashboard import insights as ins
from red_flujos.dashboard import layout as lay
from red_flujos.dashboard import network_html as net
from red_flujos.normalize import NIT_DESCONOCIDO, es_desconocido
from red_flujos.validation import ErrorValidacion

st.set_page_config(page_title="Red de flujos", layout="wide", page_icon="🔎")

# Claves de los widgets de filtro (las que restablece «Limpiar filtros»)
FILTER_KEYS = ["k_fechas", "k_sentido", "k_monto", "k_canales", "k_actores",
               "k_excl", "k_ocultar_sc", "k_top", "k_agrupar"]


if "rf_resultado" not in st.session_state:
    st.title("Red de flujos")
    st.write("Puedes empezar con datos ficticios incluidos en el proyecto.")
    if st.button("Explorar datos ficticios", type="primary"):
        try:
            with st.spinner("Preparando la demostración…"):
                st.session_state["rf_resultado"] = analizar(demo_config())
            st.session_state["rf_fuente_nombre"] = "Datos ficticios incluidos (CSV)"
            st.session_state["rf_aliases"] = {}
            st.rerun()
        except Exception as exc:
            st.error(f"No fue posible abrir la demostración ({type(exc).__name__}).")
    st.divider()
    st.write("Elige la fuente de este análisis. Ninguna conexión se abre hasta pulsar **Cargar datos**.")
    fuente = st.radio("Fuente de datos", ["Ejemplo sintético", "CSV", "Excel", "SQL Server"], key="rf_fuente")
    archivo_tx = archivo_vin = archivo_nom = None
    ruta_config = ""
    espejo = False
    if fuente in {"CSV", "Excel"}:
        extension = ["csv"] if fuente == "CSV" else ["xlsx", "xlsm"]
        archivo_tx = st.file_uploader("Flujos o transacciones", type=extension, key="rf_tx")
        archivo_vin = st.file_uploader("Relaciones (opcional)", type=extension, key="rf_vin")
        archivo_nom = st.file_uploader("Nombres de entidades (opcional)", type=extension, key="rf_nom")
        espejo = st.checkbox("La fuente registra cada flujo dos veces (emisor y receptor)", value=False)
        ruta_config = st.text_input("Ruta a YAML privado de mapeo (opcional)", value="")
        st.caption("El formato de columnas público se explica en README.md. Los archivos se procesan en memoria.")
    elif fuente == "SQL Server":
        ruta_config = st.text_input("Ruta al YAML privado con servidor, consultas y mapeo", value="")
        st.caption("Las credenciales SQL, si se necesitan, se leen de RF_SQL_USER y RF_SQL_PASSWORD.")
    if st.button("Cargar datos"):
        if fuente in {"CSV", "Excel"} and archivo_tx is None:
            st.error("Seleccione el archivo de flujos o transacciones.")
        elif fuente == "SQL Server" and not ruta_config:
            st.error("Seleccione un YAML privado para SQL Server.")
        else:
            try:
                cfg = Config.load(ruta_config or None)
                cfg.data["fuente"]["tipo"] = {
                    "Ejemplo sintético": "synthetic", "CSV": "csv", "Excel": "excel", "SQL Server": "sql"
                }[fuente]
                if fuente in {"CSV", "Excel"}:
                    cfg.data["fuente"]["archivos"] = {
                        "transacciones": archivo_tx.getvalue(),
                        "vinculados": archivo_vin.getvalue() if archivo_vin else None,
                        "nombres": archivo_nom.getvalue() if archivo_nom else None,
                    }
                    cfg.data["reconciliacion"]["modo"] = "espejo" if espejo else "ninguna"
                with st.spinner("Cargando y procesando datos…"):
                    st.session_state["rf_resultado"] = analizar(cfg)
                st.session_state["rf_fuente_nombre"] = fuente
                st.session_state["rf_aliases"] = {}
                st.rerun()
            except Exception as exc:  # la excepción SQL podría contener datos de conexión
                detalle = f" {exc}" if isinstance(exc, ErrorValidacion) else ""
                st.error(f"No fue posible cargar la fuente ({type(exc).__name__}).{detalle} Revise el YAML y los archivos.")
    st.stop()

res = st.session_state["rf_resultado"]
presentacion = res.presentacion


def money(x: float) -> str:
    return fmt.cantidad(x, presentacion)

if not len(res.df_tx):
    st.warning("La fuente elegida no produjo flujos válidos. Revise el archivo y el mapeo.")
    st.write(res.reportes.get("normalizacion", {}))
    if st.button("Elegir otra fuente"):
        st.session_state.pop("rf_resultado", None)
        st.rerun()
    st.stop()

# Alias del analista (nodos renombrados) como overlay sobre los nombres
alias_map = st.session_state.setdefault("rf_aliases", {})
mapa = {**res.mapa_nombre, **alias_map}
opt = flt.opciones(res, mapa)
nits = set(res.clientes)


def nombre_de(nit: str) -> str:
    if es_desconocido(nit):
        return "Sin contraparte"
    return mapa.get(nit) or nit


def etiqueta(nit: str) -> str:
    """Nombre e identificador de la entidad."""
    nom = nombre_de(nit)
    return nom if nom == nit or es_desconocido(nit) else f"{nom} · {nit}"


# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------
st.sidebar.title("Filtros")

# «Limpiar filtros» va ANTES de instanciar los widgets: al borrar sus claves,
# los widgets de este mismo run se crean ya con sus valores por defecto.
if st.sidebar.button("🧹 Limpiar filtros", width="stretch"):
    for k in FILTER_KEYS:
        st.session_state.pop(k, None)

st.sidebar.subheader("Período")
rango = st.sidebar.date_input(
    "Rango de fechas", value=(opt["fecha_min"], opt["fecha_max"]),
    min_value=opt["fecha_min"], max_value=opt["fecha_max"], key="k_fechas",
)
if isinstance(rango, (tuple, list)) and len(rango) == 2:
    fecha_desde, fecha_hasta = rango
else:  # el usuario está a mitad de la selección del rango
    fecha_desde, fecha_hasta = opt["fecha_min"], opt["fecha_max"]

st.sidebar.subheader("Flujos")
sentido = st.sidebar.radio(
    "Dirección", ["TODOS", "SALIDAS", "ENTRADAS"],
    format_func={"TODOS": "Todas", "SALIDAS": "Solo salidas", "ENTRADAS": "Solo entradas"}.get,
    horizontal=True, key="k_sentido",
)
monto_min_m = st.sidebar.number_input(
    f"{presentacion.get('cantidad', 'Cantidad')} mínima por evento ({presentacion.get('sufijo_escala', '')} {presentacion.get('unidad', '')})",
    min_value=0.0, value=0.0, step=1.0, key="k_monto",
    help="Filtra eventos individuales por debajo de este valor.",
)
canales = st.sidebar.multiselect("Canales", opt["canales"], default=opt["canales"], key="k_canales")
actores_sel = st.sidebar.multiselect(
    "Enfocar en actores (vacío = todos)",
    options=list(opt["actores"].keys()),
    format_func=etiqueta,
    key="k_actores",
)

with st.sidebar.expander("🚫 Excluir nodos del análisis"):
    st.caption(
        "Lo excluido desaparece de TODAS las vistas y de los KPIs "
        "(se descartan los eventos que tocan ese nodo)."
    )
    excl_opciones, excl_etiquetas = flt.opciones_nodos_excluibles(res, mapa)
    excl_sel = st.multiselect(
        "Nodos a excluir", options=excl_opciones,
        format_func=lambda nit: excl_etiquetas.get(nit, nit), key="k_excl",
    )
    ocultar_sc = st.checkbox("Ocultar «Sin contraparte»", value=False, key="k_ocultar_sc")

with st.sidebar.expander("🕸️ Vista del grafo"):
    top_lado = st.slider("Contrapartes por lado", 5, 30, 12, key="k_top")
    agrupar_otros = st.checkbox(
        "Agrupar cola larga en «Otros»", value=True, key="k_agrupar",
        help="Desactívalo para ver solo las top contrapartes, sin nodos agregados.",
    )

with st.sidebar.expander("✏️ Renombrar nodos sin nombre"):
    st.caption("Estos alias viven únicamente en esta sesión del navegador.")
    candidatos = als.sin_nombre(res, mapa)
    if candidatos:
        nit_ren = st.selectbox(
            "Nodo", candidatos,
            format_func=lambda n: f"{n}" + ("  (actor)" if n in nits else ""),
            key="k_ren_sel",
        )
        nuevo = st.text_input("Nombre a asignar", key="k_ren_txt")
        if st.button("Guardar nombre", key="k_ren_btn") and nuevo.strip():
            alias_map[nit_ren] = nuevo.strip()
            st.rerun()
    else:
        st.caption("Todos los nodos relevantes tienen nombre. ✅")
    if alias_map:
        st.markdown("**Nombres asignados**")
        st.dataframe(
            pd.DataFrame([{"ID": k, "Nombre": v} for k, v in sorted(alias_map.items())]),
            hide_index=True, width="stretch", height=140,
        )
        quitar = st.selectbox("Quitar alias", [""] + sorted(alias_map), key="k_ren_del")
        if quitar and st.button("Quitar", key="k_ren_del_btn"):
            alias_map.pop(quitar, None)
            st.rerun()

st.sidebar.divider()
st.sidebar.caption(
    f"**Fuente:** {st.session_state.get('rf_fuente_nombre', '')} · "
    f"**Universo cargado:** {len(res.df_tx):,} eventos"
)
if st.sidebar.button("Cambiar fuente de datos", width="stretch"):
    st.session_state.pop("rf_resultado", None)
    st.session_state.pop("rf_aliases", None)
    st.rerun()

# ---------------------------------------------------------------------------
# Aplicar filtros + reconstruir grafo de la vista
# ---------------------------------------------------------------------------
excluidos = set(excl_sel) | ({NIT_DESCONOCIDO} if ocultar_sc else set())
df_f = flt.aplicar(
    res, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta,
    monto_min=monto_min_m * float(presentacion.get("escala", 1) or 1), canales=canales, sentido=sentido,
    actores_foco=actores_sel or None, excluir_nodos=excluidos or None,
)
G_col, df_aristas_canal = flt.reconstruir_grafo(res, df_f, mapa)

# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------
externos_vista = [n for n in G_col.nodes() if n not in nits and not es_desconocido(n)]
n_toca_sc = int((df_f["destino"].map(es_desconocido) | df_f["origen"].map(es_desconocido)).sum())
k = st.columns(5)
k[0].metric("Eventos", f"{len(df_f):,}",
            help=f"De {len(res.df_tx):,} cargadas de la fuente.")
k[1].metric(f"{presentacion.get('cantidad', 'Cantidad')} total", money(float(df_f["valor"].sum())))
k[2].metric("Actores en vista", f"{len([n for n in G_col.nodes() if n in nits])}")
k[3].metric("Contrapartes", f"{len(externos_vista)}")
k[4].metric("% sin contraparte", f"{(n_toca_sc/len(df_f)*100 if len(df_f) else 0):.0f}%",
            help="Eventos sin contraparte identificada.")
st.caption(f"Mostrando {len(df_f):,} de {len(res.df_tx):,} eventos cargados.")

if not len(df_f):
    st.info("Ningún dato cumple los filtros actuales. Usa «🧹 Limpiar filtros» para restablecer.")
    st.stop()

# ---------------------------------------------------------------------------
# Pestañas
# ---------------------------------------------------------------------------
t_resumen, t_red, t_sankey, t_flujos, t_estruct, t_datos = st.tabs(
    ["📋 Resumen", "🕸️ Red de flujos", "📊 Canales por actor", "🔁 Flujos entre actores",
     f"🏢 {presentacion.get('relaciones', 'Relaciones')}", "📄 Datos"]
)

with t_resumen:
    st.caption("Lectura rápida del flujo entre las partes para los filtros actuales.")
    bullets = ins.generar_bullets(df_f, G_col, nits, nombre_de, presentacion)
    st.markdown("\n".join(f"- {b}" for b in bullets))

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Top actores monitoreados** (por {presentacion.get('cantidad', 'cantidad').lower()})")
        t = ins.top_por_tipo(G_col, "cliente", n=8, por="monto_total")
        if len(t):
            t = t.copy()
            t["recibido"] = t["recibido"].map(money)
            t["enviado"] = t["enviado"].map(money)
            st.dataframe(t[["nombre", "nit", "recibido", "enviado", "n_tx"]]
                         .rename(columns={"n_tx": "# eventos"}), hide_index=True, width="stretch")
        else:
            st.caption("Sin datos.")
    with c2:
        st.markdown(f"**Top contrapartes externas** (por {presentacion.get('cantidad', 'cantidad').lower()})")
        t = ins.top_por_tipo(G_col, "externo", n=8, por="monto_total")
        if len(t):
            t = t.copy()
            t["recibido"] = t["recibido"].map(money)
            t["enviado"] = t["enviado"].map(money)
            st.dataframe(t[["nombre", "nit", "recibido", "enviado", "n_tx"]]
                         .rename(columns={"n_tx": "# eventos"}), hide_index=True, width="stretch")
        else:
            st.caption("Sin datos.")

    c3, c4 = st.columns(2)
    with c3:
        st.markdown(f"**Flujos entre actores — top por {presentacion.get('cantidad', 'cantidad').lower()}**")
        fl = flujos_entre_actores(G_col, nits)
        fl_reales = fl[~fl["mismo_actor"]] if len(fl) else fl
        if len(fl_reales):
            t = fl_reales.sort_values("total", ascending=False).head(8).copy()
            t["monto"] = t["total"].map(money)
            t["origen"] = t["origen"].map(etiqueta)
            t["destino"] = t["destino"].map(etiqueta)
            st.dataframe(
                t[["origen", "destino", "monto", "n_tx"]].rename(columns={"n_tx": "# eventos", "monto": presentacion.get("cantidad", "Cantidad")}),
                hide_index=True, width="stretch",
            )
        else:
            st.caption("Sin flujos entre actores distintos.")
    with c4:
        st.markdown("**Flujos entre actores — top por número de eventos**")
        if len(fl_reales):
            t = fl_reales.sort_values("n_tx", ascending=False).head(8).copy()
            t["monto"] = t["total"].map(money)
            t["origen"] = t["origen"].map(etiqueta)
            t["destino"] = t["destino"].map(etiqueta)
            st.dataframe(
                t[["origen", "destino", "monto", "n_tx"]].rename(columns={"n_tx": "# eventos", "monto": presentacion.get("cantidad", "Cantidad")}),
                hide_index=True, width="stretch",
            )
        else:
            st.caption("Sin flujos entre actores distintos.")

    st.markdown("**Desglose por canal**")
    dc = ins.desglose_canal(df_f, n=10).copy()
    if len(dc):
        dc["monto"] = dc["monto"].map(money)
        st.dataframe(dc[["canal", "monto", "n_tx"]].rename(columns={"n_tx": "# eventos", "monto": presentacion.get("cantidad", "Cantidad")}),
                     hide_index=True, width="stretch")
    else:
        st.caption("Sin datos.")

with t_red:
    if G_col.number_of_nodes() == 0:
        st.info("No hay nodos para mostrar con los filtros actuales.")
    else:
        G_vis, pos, meta = lay.preparar_visual(
            G_col, nits, top_por_lado=top_lado, mostrar_otros=agrupar_otros
        )
        st.iframe(net.red_transaccional_html(G_vis, pos, height=620, presentacion=presentacion), height=650)
        c1, c2 = st.columns([3, 2])
        with c1:
            st.caption(
                "🖱️ **Arrastra los nodos** para reorganizar · rueda = zoom · "
                "las **flechas** indican la dirección · grosor ∝ cantidad."
            )
        with c2:
            st.caption(
                f"{meta['n_actores']} actores · emisores {meta['n_emisores_mostrados']}"
                f"(+{meta['n_emisores_colapsados']} en «Otros») · "
                f"receptores {meta['n_receptores_mostrados']}"
                f"(+{meta['n_receptores_colapsados']} en «Otros»)"
            )
        st.markdown(
            "🔵 Actor monitoreado &nbsp;·&nbsp; ⚪ Contraparte &nbsp;·&nbsp; "
            "🟡 Otros (agregado) &nbsp;·&nbsp; 🟣 Sin contraparte",
            help="La leyenda aplica al grafo de arriba.",
        )

with t_sankey:
    canal_mod = canal_modalidad_actor(df_f, nits)
    actores_con_datos = [n for n in opt["actores"] if n in set(canal_mod["actor"])]
    if not actores_con_datos:
        st.info("Ningún actor con movimientos por canal en el filtro actual.")
    else:
        c_sel, c_mod, c_top = st.columns([3, 1.4, 1.6])
        with c_sel:
            sel = st.selectbox("Actor", actores_con_datos, format_func=etiqueta)
        with c_mod:
            con_mod = st.checkbox("Incluir modalidad", value=True)
        with c_top:
            top_mod = st.slider("Modalidades por lado", 3, 15, 8, disabled=not con_mod)

        sub = canal_mod[canal_mod["actor"] == sel]
        tot_in = float(sub.loc[sub["sentido"] == "ENTRA", "total"].sum())
        tot_out = float(sub.loc[sub["sentido"] == "SALE", "total"].sum())
        m1, m2, m3 = st.columns(3)
        m1.metric("Entra", money(tot_in))
        m2.metric("Sale", money(tot_out))
        m3.metric("Neto", money(tot_in - tot_out))

        st.plotly_chart(
            fig.figura_sankey_actor(canal_mod, sel, etiqueta(sel),
                                    incluir_modalidad=con_mod, top_modalidades=top_mod,
                                    presentacion=presentacion),
            width="stretch",
        )
        st.caption("🔵 Azul = entrada · 🟠 Naranja = salida. "
                   "Extremos = modalidad · nivel medio = canal.")
        vista = sub.copy()
        vista["monto"] = vista["total"].map(money)
        st.dataframe(
            vista[["sentido", "canal", "nombre_tx", "monto", "n_tx"]]
            .rename(columns={"nombre_tx": "modalidad", "n_tx": "# eventos", "monto": presentacion.get("cantidad", "Cantidad")}),
            hide_index=True, width="stretch",
        )

with t_flujos:
    flujos = flujos_entre_actores(G_col, nits)
    if not len(flujos):
        st.info("Sin flujos entre actores monitoreados con los filtros actuales.")
    else:
        st.plotly_chart(fig.figura_heatmap_actores(flujos, metrica="total", presentacion=presentacion), width="stretch")
        st.plotly_chart(fig.figura_heatmap_actores(flujos, metrica="n_tx", presentacion=presentacion), width="stretch")
        vista = flujos.copy()
        vista["tipo"] = vista["mismo_actor"].map({True: "mismo actor", False: "entre actores"})
        vista["monto"] = vista["total"].map(money)
        vista["origen"] = vista["origen"].map(etiqueta)
        vista["destino"] = vista["destino"].map(etiqueta)
        st.dataframe(
            vista[["origen", "destino", "tipo", "monto", "n_tx"]].rename(columns={"n_tx": "# eventos", "monto": presentacion.get("cantidad", "Cantidad")}),
            hide_index=True, width="stretch",
        )

with t_estruct:
    st.caption("Relaciones de las entidades monitoreadas. Esta vista no depende de los filtros de flujo.")
    if res.G_estructura.number_of_edges() == 0:
        st.info("La fuente elegida no incluyó relaciones.")
    else:
        nits_hub = set(res.hubs["nit_vinculado"]) if len(res.hubs) else set()
        st.iframe(net.estructura_html(res.G_estructura, mapa, nits_hub, height=540,
                                     presentacion=presentacion), height=570)
        st.caption(
            "⬛ Entidad · 🟢 Relacionado · 🔴 Nodo compartido por varias entidades. "
            "Arrastra para reorganizar; la etiqueta de la línea es la relación."
        )
        with st.expander("Relacionados compartidos (tabla)"):
            if len(res.hubs):
                st.dataframe(res.hubs[["nombre_vinculado", "n_empresas", "relaciones"]],
                             hide_index=True, width="stretch")
            else:
                st.caption("Ninguno supera el umbral.")
        with st.expander("Pares de entidades con relación compartida (tabla)"):
            if len(res.pares_estructura):
                pv = res.pares_estructura.copy()
                pv["empresa_a"] = pv["empresa_a"].map(etiqueta)
                pv["empresa_b"] = pv["empresa_b"].map(etiqueta)
                st.dataframe(pv[["empresa_a", "empresa_b", "relacion", "nombre_vinculado"]],
                             hide_index=True, width="stretch")
            else:
                st.caption("Sin pares con vínculo compartido.")

with t_datos:
    st.caption(f"{len(df_f):,} eventos tras los filtros (se muestran hasta 1.000).")
    with st.expander("Calidad de la carga y reconciliación"):
        st.write("Normalización", res.reportes.get("normalizacion", {}))
        st.write("Reconciliación", res.reportes.get("dedup", {}))
        hom = res.reportes.get("homologacion", {})
        st.write("Identidades", {
            "uniones": hom.get("uniones", 0),
            "conflictos": hom.get("conflictos", []),
            "grupos_multi_id": hom.get("grupos_multi_nit", {}),
        })
    cols = ["fecha", "origen", "destino", "canal", "sentido", "valor", "nombre_tx", "transaccion"]
    cols = [c for c in cols if c in df_f.columns]
    vista = df_f[cols].head(1000).copy()
    vista["origen"] = vista["origen"].map(etiqueta)
    vista["destino"] = vista["destino"].map(etiqueta)
    st.dataframe(vista, hide_index=True, width="stretch")
    st.download_button(
        "⬇️ Descargar CSV filtrado (completo, valores crudos)",
        df_f[cols].to_csv(index=False).encode("utf-8"),
        file_name="transacciones_filtradas.csv", mime="text/csv",
    )
