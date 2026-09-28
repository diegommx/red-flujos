"""Orquestador del pipeline: une todas las etapas en una sola llamada."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import networkx as nx
import pandas as pd

from . import analytics as an
from . import graphs as gr
from . import homologate as ho
from . import normalize as nm
from .config import Config
from .dedup import deduplicar
from .sources import build_source
from .validation import LOG, get_logger


@dataclass
class Resultado:
    """Todo lo que produce el motor para un análisis."""

    clientes: dict[str, str]
    df_tx: pd.DataFrame                      # transaccional deduplicada (con origen/destino/canal)
    df_vin: pd.DataFrame                     # vinculados normalizada y homologada
    G_col: nx.DiGraph                        # grafo transaccional colapsado
    G_principal: nx.DiGraph                  # subgrafo tras filtros (incluye SIN_CONTRAPARTE, para visual)
    G_topologia: nx.DiGraph                  # = G_principal sin SIN_CONTRAPARTE (para centralidad/ciclos)
    G_estructura: nx.MultiDiGraph            # grafo societario
    df_aristas_canal: pd.DataFrame           # origen-destino-canal (alimenta Sankey)
    resumen_nodos: pd.DataFrame
    metricas: pd.DataFrame
    ciclos: list
    flujos_actores: pd.DataFrame             # dinero entre monitoreados
    canal_actor: pd.DataFrame                # entra/sale por canal por actor
    hubs: pd.DataFrame                       # vinculados-hub (bandera)
    pares_estructura: pd.DataFrame           # empresas con vínculo compartido
    mapa_nombre: dict[str, str] = field(default_factory=dict)   # NIT canónico -> nombre (para reconstruir grafos)
    filtros: dict[str, Any] = field(default_factory=dict)       # filtros del subgrafo (config.yaml)
    reportes: dict[str, Any] = field(default_factory=dict)
    presentacion: dict[str, Any] = field(default_factory=dict)


def analizar(cfg: Config) -> Resultado:
    get_logger(nivel=cfg["logging"]["nivel"])
    reportes: dict[str, Any] = {}

    # 1) Ingesta
    fuente = build_source(cfg)
    df_tx_raw = fuente.fetch_transacciones()
    df_vin_raw = fuente.fetch_vinculados()

    # 2) Normalización transaccional + detección de clientes
    df, rep_norm = nm.normalizar_transaccional(df_tx_raw, cfg)
    reportes["normalizacion"] = rep_norm
    clientes = nm.detectar_clientes(df, cfg)
    nits_conocidos = set(clientes)

    # 3) Homologación de contrapartes
    mapa_nit, mapa_nombre, rep_hom = ho.homologar(
        df, nits_conocidos, cfg.unir_nits, modo=cfg.homologacion.get("modo", "exacta")
    )
    reportes["homologacion"] = rep_hom
    df = ho.aplicar(df, mapa_nit)

    # 4) Dedup espejo + origen/destino
    modo_reconciliacion = cfg.reconciliacion.get("modo", "auto")
    if modo_reconciliacion == "auto":
        modo_reconciliacion = "espejo" if cfg["fuente"]["tipo"] == "synthetic" else "ninguna"
    df_todas, rep_dedup = deduplicar(df, nits_conocidos, modo=modo_reconciliacion)
    reportes["dedup"] = rep_dedup

    # 5) Vinculados (comparten NIT canónico con la capa transaccional)
    df_vin = nm.normalizar_vinculados(df_vin_raw, cfg, mapa_nit)

    # 5b) Enriquecimiento de nombres. Precedencia (de menor a mayor):
    #     homologación (Nombre_Contraparte) < NombreEmpresa (JOIN de Vinculados)
    #     < nombres de la fuente opcional. Los alias del analista se
    #     aplican encima de todo, pero en la capa del dashboard.
    n_enr = 0
    emp_nombres = (
        df_vin[df_vin["nombre_empresa"] != ""]
        .drop_duplicates(subset="nit_empresa")
        .set_index("nit_empresa")["nombre_empresa"]
        .to_dict()
    )
    for nit, nom in emp_nombres.items():
        if mapa_nombre.get(nit, "") != nom:
            mapa_nombre[nit] = nom
            n_enr += 1
    df_nombres = nm.normalizar_nombres_clientes(fuente.fetch_nombres_clientes(), cfg)
    for _, r in df_nombres.iterrows():
        nit_can = mapa_nit.get(r["nit"], r["nit"])
        if mapa_nombre.get(nit_can, "") != r["nombre"]:
            mapa_nombre[nit_can] = r["nombre"]
            n_enr += 1
    LOG.info("Nombres enriquecidos desde tablas opcionales: %d", n_enr)

    # 6) Grafos
    G_col, df_aristas_canal = gr.construir_grafo_transaccional(
        df_todas, nits_conocidos, clientes, mapa_nombre
    )
    G_principal = gr.subgrafo_principal(G_col, nits_conocidos, cfg.filtros)
    G_topologia = gr.subgrafo_topologia(G_principal)   # sin SIN_CONTRAPARTE
    G_estructura = gr.construir_grafo_estructural(df_vin)

    # 7) Analítica
    resumen = an.resumen_nodos(G_col)                        # SIN_CONTRAPARTE sí participa aquí (es una cifra útil por actor)
    metricas = an.metricas_centralidad(G_topologia)           # SIN_CONTRAPARTE excluido (distorsiona centralidad)
    ciclos = an.ciclos_cortos(G_topologia)                     # SIN_CONTRAPARTE excluido (evita ciclos falsos)
    flujos_actores = an.flujos_entre_actores(G_col, nits_conocidos)
    canal_actor = an.canal_por_actor(df_aristas_canal, nits_conocidos)
    hubs, pares = an.estructura_compartida(df_vin, cfg.vinculados.get("umbral_hub", 3))

    return Resultado(
        clientes=clientes,
        df_tx=df_todas,
        df_vin=df_vin,
        G_col=G_col,
        G_principal=G_principal,
        G_topologia=G_topologia,
        G_estructura=G_estructura,
        df_aristas_canal=df_aristas_canal,
        resumen_nodos=resumen,
        metricas=metricas,
        ciclos=ciclos,
        flujos_actores=flujos_actores,
        canal_actor=canal_actor,
        hubs=hubs,
        pares_estructura=pares,
        mapa_nombre=mapa_nombre,
        filtros=dict(cfg.filtros),
        reportes=reportes,
        presentacion=cfg.presentacion,
    )
