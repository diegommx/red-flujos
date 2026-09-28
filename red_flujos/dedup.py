"""Dirección del flujo y reconciliación conservadora de observaciones espejo."""
from __future__ import annotations

import pandas as pd

from .normalize import es_desconocido
from .validation import LOG


def deduplicar(
    df: pd.DataFrame,
    nits_conocidos: set[str],
    modo: str = "ninguna",
) -> tuple[pd.DataFrame, dict]:
    """Materializa origen/destino y opcionalmente reconcilia espejo.

    Sólo se retira un crédito cuando existe exactamente un débito interno con
    mismo origen, destino, instante, cantidad y canal. Grupos ambiguos se
    conservan íntegros para revisión. ``ninguna`` es seguro para fuentes que
    registran cada evento una vez.
    """
    if modo not in {"ninguna", "espejo"}:
        raise ValueError("reconciliacion.modo debe ser 'ninguna' o 'espejo'")
    df = df.copy()
    df["origen"] = df["nit"].where(df["sentido"] == "DEBITO", df["nit_contraparte"])
    df["destino"] = df["nit_contraparte"].where(df["sentido"] == "DEBITO", df["nit"])
    inicial = len(df)

    # Un mismo identificador de fila no debe contabilizarse dos veces.
    repetidas = 0
    if "id_operacion" in df.columns:
        ids = df["id_operacion"].fillna("").astype(str).str.strip()
        campos = ["id_operacion", "nit", "nit_contraparte", "sentido", "fecha", "valor", "canal"]
        repetido = ids.ne("") & df.duplicated(subset=campos, keep="first")
        repetidas = int(repetido.sum())
        df = df.loc[~repetido].copy()

    interna = (
        df["origen"].isin(nits_conocidos) & df["destino"].isin(nits_conocidos)
        & ~df["origen"].map(es_desconocido) & ~df["destino"].map(es_desconocido)
    )
    creditos_eliminados = 0
    ambiguas = 0
    if modo == "espejo" and interna.any():
        pendientes = df.loc[interna].copy()
        clave = ["origen", "destino", "fecha", "valor", "canal"]
        eliminar = []
        for _, grupo in pendientes.groupby(clave, dropna=False, sort=False):
            debitos = grupo[grupo["sentido"] == "DEBITO"]
            creditos = grupo[grupo["sentido"] == "CREDITO"]
            if len(debitos) == 1 and len(creditos) == 1:
                eliminar.append(creditos.index[0])
            elif len(debitos) and len(creditos):
                ambiguas += len(grupo)
        creditos_eliminados = len(eliminar)
        df = df.drop(index=eliminar)

    internas_mask = df["origen"].isin(nits_conocidos) & df["destino"].isin(nits_conocidos)
    internas_finales = int(internas_mask.sum())
    reporte = {
        "modo": modo,
        "filas_brutas": inicial,
        "duplicados_id": repetidas,
        "internas_brutas": int(interna.sum()),
        "espejos_reconciliados": creditos_eliminados,
        "grupos_ambiguos_filas": ambiguas,
        "internas_finales": internas_finales,
        "debitos_canonicos": int((internas_mask & (df["sentido"] == "DEBITO")).sum()),
        "creditos_huerfanos": int((internas_mask & (df["sentido"] == "CREDITO")).sum()),
        "externas": len(df) - internas_finales,
        "total_final": len(df),
    }
    LOG.info("Reconciliación %s: %d observaciones -> %d eventos; %d espejos; %d filas ambiguas",
             modo, inicial, len(df), creditos_eliminados, ambiguas)
    return df.reset_index(drop=True), reporte
