"""Resolución conservadora de identidad para el perfil financiero inicial."""
from __future__ import annotations

import re

import pandas as pd

from .normalize import es_desconocido
from .validation import LOG


def normalizar_nombre(valor) -> str:
    if not isinstance(valor, str):
        return ""
    valor = valor.upper().strip().replace("_", " ")
    return re.sub(r"\s+", " ", re.sub(r"\s*-\s*$", "", valor)).strip()


def _es_prefijo(a: str, b: str) -> bool:
    return bool(a and b and a != b and (a.startswith(b) or b.startswith(a)))


class _UnionFind:
    def __init__(self, ids: list[str], monitoreados: set[str]):
        self.parent = list(range(len(ids)))
        self.monitoreados = [{ids[i]} & monitoreados for i in range(len(ids))]

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, i: int, j: int) -> bool:
        a, b = self.find(i), self.find(j)
        if a == b:
            return False
        if len(self.monitoreados[a] | self.monitoreados[b]) > 1:
            raise ValueError("La homologación intentó unir dos actores monitoreados distintos")
        self.parent[b] = a
        self.monitoreados[a] |= self.monitoreados[b]
        return True


def homologar(
    df: pd.DataFrame,
    nits_conocidos: set[str],
    unir_nits: dict | None = None,
    modo: str = "exacta",
):
    """Devuelve mapa de IDs, nombres y decisiones de homologación.

    ``exacta`` une sólo el mismo ID. ``prefijo`` permite variantes de ID
    compatibles con el mismo nombre, bajo revisión del reporte generado.
    Las fusiones manuales siempre se registran y nunca unen monitoreados
    distintos.
    """
    if modo not in {"exacta", "prefijo"}:
        raise ValueError("homologacion.modo debe ser 'exacta' o 'prefijo'")
    unir_nits = {str(k): str(v) for k, v in (unir_nits or {}).items()}
    propios = df[["nit", "nombre"]].drop_duplicates().rename(columns={"nit": "id", "nombre": "nombre_raw"})
    contras = df[["nit_contraparte", "nombre_contraparte"]].drop_duplicates().rename(
        columns={"nit_contraparte": "id", "nombre_contraparte": "nombre_raw"}
    )
    catalogo = pd.concat([propios, contras], ignore_index=True)
    catalogo = catalogo[(catalogo["id"] != "") & ~catalogo["id"].map(es_desconocido)].copy()
    catalogo["nombre_norm"] = catalogo["nombre_raw"].map(normalizar_nombre)
    catalogo = catalogo.drop_duplicates(["id", "nombre_norm"]).reset_index(drop=True)
    if catalogo.empty:
        return {}, {}, {"pares_candidatos": 0, "uniones": 0, "decisiones": [],
                        "grupos_totales": 0, "grupos_multi_nit": {}, "nombres_en_varios_nits": {}}

    ids = catalogo["id"].tolist()
    nombres = catalogo["nombre_norm"].tolist()
    uf = _UnionFind(ids, nits_conocidos)
    por_id: dict[str, list[int]] = {}
    for i, entity_id in enumerate(ids):
        por_id.setdefault(entity_id, []).append(i)
    candidatos: set[tuple[int, int]] = set()
    for indices in por_id.values():
        candidatos.update((indices[i], indices[j]) for i in range(len(indices)) for j in range(i + 1, len(indices)))
    if modo == "prefijo":
        ids_unicos = sorted(por_id)
        for i, a in enumerate(ids_unicos):
            for b in ids_unicos[i + 1:]:
                if _es_prefijo(a, b):
                    for ai in por_id[a]:
                        for bi in por_id[b]:
                            if nombres[ai] and nombres[ai] == nombres[bi]:
                                candidatos.add((ai, bi))

    decisiones = []
    conflictos = []
    for i, j in sorted(candidatos):
        if uf.find(i) == uf.find(j):
            continue
        try:
            if uf.union(i, j):
                decisiones.append({"a": ids[i], "b": ids[j],
                                   "regla": "id_exacto" if ids[i] == ids[j] else "prefijo_y_nombre"})
        except ValueError:
            conflictos.append({"a": ids[i], "b": ids[j], "regla": "conflicto_monitoreados"})

    for secundario, canonico in sorted(unir_nits.items()):
        if secundario not in por_id or canonico not in por_id:
            raise ValueError(f"Fusión manual con ID ausente: {secundario} -> {canonico}")
        if secundario == canonico:
            continue
        uf.union(por_id[secundario][0], por_id[canonico][0])
        decisiones.append({"a": secundario, "b": canonico, "regla": "manual"})

    grupos: dict[int, list[int]] = {}
    for i in range(len(catalogo)):
        grupos.setdefault(uf.find(i), []).append(i)

    mapa_id: dict[str, str] = {}
    mapa_nombre: dict[str, str] = {}
    grupos_multi: dict[str, dict] = {}
    for indices in grupos.values():
        miembros = sorted({ids[i] for i in indices})
        monitoreados = sorted(set(miembros) & nits_conocidos)
        preferidos = sorted(set(unir_nits.values()) & set(miembros))
        canonico = monitoreados[0] if monitoreados else (preferidos[0] if preferidos else max(miembros, key=lambda x: (len(x), x)))
        for member in miembros:
            mapa_id[member] = canonico
        nombres_grupo = [nombres[i] for i in indices if nombres[i]]
        mapa_nombre[canonico] = max(nombres_grupo, key=lambda x: (len(x), x)) if nombres_grupo else ""
        if len(miembros) > 1:
            grupos_multi[canonico] = {"n_variantes": len(miembros), "nits": miembros}

    por_nombre: dict[str, set[str]] = {}
    for i, nombre in enumerate(nombres):
        if nombre:
            por_nombre.setdefault(nombre, set()).add(mapa_id[ids[i]])
    sospechas = {nombre: len(entidades) for nombre, entidades in por_nombre.items() if len(entidades) > 1}
    reporte = {
        "pares_candidatos": len(candidatos),
        "uniones": len(decisiones),
        "decisiones": decisiones,
        "conflictos": conflictos,
        "grupos_totales": len(grupos),
        "grupos_multi_nit": grupos_multi,
        "nombres_en_varios_nits": sospechas,
    }
    LOG.info("Homologación: %d uniones | %d conflictos | %d grupos", len(decisiones), len(conflictos), len(grupos))
    return mapa_id, mapa_nombre, reporte


def aplicar(df: pd.DataFrame, mapa_nit: dict) -> pd.DataFrame:
    df = df.copy()
    df["nit"] = df["nit"].map(lambda n: mapa_nit.get(n, n))
    df["nit_contraparte"] = df["nit_contraparte"].map(lambda n: mapa_nit.get(n, n))
    return df
