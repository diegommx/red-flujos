"""Normalización de la tabla transaccional.

El **sentido** del flujo se deriva de ``Transaccion`` (RETIRO = sale/débito,
CONSIGNACION = entra/crédito). Todo lo demás se excluye del análisis de flujo:
``PROD-CREDITOS`` (pagos de crédito) y los registros vacíos/NULL. Se reporta el
conteo de exclusiones por cada valor de ``Transaccion``.

``NombreTX`` NO define la dirección: describe la *modalidad* del movimiento
(p. ej. "Retiro de Cuenta en Efectivo"). Se conserva como atributo descriptivo
para desgloses secundarios. El canal del análisis es ``Canal``.
"""
from __future__ import annotations

import unicodedata

import pandas as pd

from .config import Config
from .validation import LOG, exigir

NIT_DESCONOCIDO = "SIN_CONTRAPARTE"


def es_desconocido(identificador: str) -> bool:
    """Un extremo sin identificar nunca representa una identidad compartida."""
    return str(identificador) == NIT_DESCONOCIDO or str(identificador).startswith(NIT_DESCONOCIDO + ":")


def normalizar_nit(serie: pd.Series) -> pd.Series:
    """Conserva identificadores como texto, incluidos IP, UUID y ceros iniciales.

    El nombre se mantiene por compatibilidad con la API financiera inicial.
    Un número de punto flotante grande se rechaza: su precisión puede haber
    cambiado antes de llegar al motor y no es seguro inventar una identidad.
    """
    def convertir(valor):
        if pd.isna(valor):
            return ""
        if isinstance(valor, float):
            if not valor.is_integer() or abs(valor) > 2**53:
                raise ValueError("Identificador numérico impreciso; léalo como texto")
            return str(int(valor))
        return str(valor).strip()

    return serie.map(convertir)


def _parsear_fecha(serie: pd.Series) -> pd.Series:
    f = pd.to_datetime(serie, errors="coerce")
    faltan = f.isna()
    if faltan.any():  # reintento DD/MM/YYYY solo para las que no parsean
        f.loc[faltan] = pd.to_datetime(serie[faltan], dayfirst=True, errors="coerce")
    return f


def normalizar_tipo_persona(valor, juridica_valores) -> str:
    s = str(valor).upper().strip()
    if s in {"", "NAN", "NONE", "ND"}:
        return "ND"
    return "PJ" if s in juridica_valores else "PN"


def _sin_acentos(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def clasificar_sentido_transaccion(transaccion, mapa_sentido: dict[str, str]) -> str:
    """DEBITO (sale) / CREDITO (entra) / '' (excluida) según Transaccion.

    Las claves de ``mapa_sentido`` se comparan sin acentos y en mayúsculas, de
    modo que 'CONSIGNACION' y 'CONSIGNACIÓN' se tratan igual. Cualquier valor no
    mapeado (PROD-CREDITOS, vacíos, NULL) devuelve '' y queda fuera del flujo.
    """
    t = _sin_acentos(str(transaccion).upper().strip())
    return mapa_sentido.get(t, "")


def normalizar_transaccional(df_raw: pd.DataFrame, cfg: Config) -> tuple[pd.DataFrame, dict]:
    """Devuelve (df_normalizado, reporte)."""
    col = cfg.col_tx
    presentes = {c: destino for c, destino in col.items() if c in df_raw.columns}
    obligatorias = {"nit", "nit_contraparte", "fecha_str", "valor", "transaccion"}
    faltantes = sorted(obligatorias - set(presentes.values()))
    exigir(not faltantes, f"Columnas de flujo faltantes: {faltantes}")

    df = df_raw[list(presentes)].rename(columns=presentes).copy()
    for opcional in ("id_operacion", "canal", "nombre_tx", "tipo_persona_nit", "nombre_contraparte"):
        if opcional not in df.columns:
            df[opcional] = ""

    # La consulta no trae nombre propio del titular -> se resolverá por homologación
    if "nombre" not in df.columns:
        df["nombre"] = ""
    df["nombre"] = df["nombre"].fillna("").astype(str).str.strip()

    # Canal (dimensión del análisis). 'NULL'/'' -> SIN_CANAL
    df["canal"] = df["canal"].fillna("").astype(str).str.strip().str.upper()
    df["canal"] = df["canal"].where(~df["canal"].isin(["", "NULL"]), "SIN_CANAL")

    # NombreTX: modalidad del movimiento (atributo descriptivo, NO dirección)
    df["nombre_tx"] = df["nombre_tx"].fillna("").astype(str).str.strip()

    # Transaccion (fuente de la dirección)
    df["transaccion"] = df["transaccion"].fillna("").astype(str).str.strip()

    # Identificadores (el nombre interno 'nit' se conserva temporalmente)
    df["nit"] = normalizar_nit(df["nit"])
    df["nit_contraparte"] = normalizar_nit(df["nit_contraparte"])
    exigir(
        not (df["nit"].map(es_desconocido) | df["nit_contraparte"].map(es_desconocido)).any(),
        "Un ID de entrada usa el prefijo reservado SIN_CONTRAPARTE",
    )

    # Fecha y cantidad
    df["fecha"] = _parsear_fecha(df["fecha_str"])
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")

    # Sentido desde Transaccion (RETIRO=DEBITO, CONSIGNACION=CREDITO)
    df["sentido"] = df["transaccion"].apply(
        lambda x: clasificar_sentido_transaccion(x, cfg.mapa_sentido)
    )
    # Exclusiones por valor de Transaccion (PROD-CREDITOS, vacíos/NULL, otros)
    _excl = df.loc[df["sentido"] == "", "transaccion"].copy()
    _excl = _excl.where(_excl.str.strip() != "", "(vacío/NULL)")
    transaccion_excluidas = _excl.value_counts().to_dict()
    n_excluidas = int((df["sentido"] == "").sum())

    # Limpieza de filas inválidas
    antes = len(df)
    rechazos = {
        "fecha_invalida": int(df["fecha"].isna().sum()),
        "actor_vacio": int((df["nit"] == "").sum()),
        "cantidad_invalida": int((df["valor"].isna() | (df["valor"] <= 0)).sum()),
        "tipo_evento_no_mapeado": n_excluidas,
    }
    df = df.dropna(subset=["fecha"]).copy()
    df = df[df["nit"] != ""].copy()
    df = df[df["valor"] > 0].copy()
    df = df[df["sentido"] != ""].copy()  # excluye PROD-CREDITOS, vacíos/NULL
    descartadas = antes - len(df)

    # Contrapartes vacías
    df = df.reset_index(drop=True)
    vacias = df["nit_contraparte"] == ""
    # Un extremo distinto por fila evita caminos y agregaciones falsos.
    df.loc[vacias, "nit_contraparte"] = [f"{NIT_DESCONOCIDO}:{i}" for i in df.index[vacias]]
    df["nombre_contraparte"] = df["nombre_contraparte"].fillna("").astype(str).str.strip()

    # TipoPersona -> PN/PJ
    df["tipo_persona_nit"] = df["tipo_persona_nit"].apply(
        lambda v: normalizar_tipo_persona(v, cfg.juridica_valores)
    )

    reporte = {
        "filas_validas": len(df),
        "descartadas": descartadas,
        "rechazos_por_motivo": rechazos,
        "sin_contraparte": int(vacias.sum()),
        "transaccion_excluidas_total": n_excluidas,
        "transaccion_excluidas": transaccion_excluidas,
        "rango": (
            (df["fecha"].min().date(), df["fecha"].max().date()) if len(df) else (None, None)
        ),
        "distribucion_sentido": df["sentido"].value_counts().to_dict(),
        "distribucion_canal": df["canal"].value_counts().to_dict(),
    }
    LOG.info(
        "Normalización: %d válidas | %d descartadas | %d sin contraparte | %d excluidas por Transaccion",
        reporte["filas_validas"], descartadas, reporte["sin_contraparte"], n_excluidas,
    )
    if transaccion_excluidas:
        LOG.info("Excluidas por Transaccion: %s", transaccion_excluidas)
    return df, reporte


def detectar_clientes(df: pd.DataFrame, cfg: Config) -> dict[str, str]:
    """Actores monitoreados = NIT únicos de la columna 'nit' (o dict manual)."""
    if not cfg.auto_detectar_clientes:
        return {str(k): str(v).upper() for k, v in cfg.clientes_manual.items()}

    det = (
        df[df["nit"] != ""]
        .groupby(["nit", "tipo_persona_nit"], dropna=False)
        .size()
        .reset_index(name="n")
        .drop_duplicates(subset="nit")
    )
    clientes = {row["nit"]: row["tipo_persona_nit"] for _, row in det.iterrows()}
    LOG.info(
        "Clientes detectados: %d (%d PN + %d PJ)",
        len(clientes),
        sum(v == "PN" for v in clientes.values()),
        sum(v == "PJ" for v in clientes.values()),
    )
    return clientes


def normalizar_vinculados(df_raw: pd.DataFrame, cfg: Config, mapa_nit: dict | None = None) -> pd.DataFrame:
    """Normaliza la tabla de vinculados y opcionalmente homologa sus NITs."""
    if df_raw is None or df_raw.empty:
        return pd.DataFrame(columns=["nit_empresa", "nombre_empresa", "nit_vinculado",
                                     "nombre_vinculado", "relacion", "estado", "codigo_ciiu"])
    col = cfg.col_vin
    presentes = {k: v for k, v in col.items() if k in df_raw.columns}
    obligatorias = {"nit_empresa", "nit_vinculado", "relacion"}
    faltantes = sorted(obligatorias - set(presentes.values()))
    exigir(not faltantes, f"Columnas faltantes en la consulta de vinculados: {faltantes}")

    df = df_raw[list(presentes.keys())].rename(columns=presentes).copy()
    for opcional in ("nombre_empresa", "nombre_vinculado", "estado", "codigo_ciiu"):
        if opcional not in df.columns:
            df[opcional] = ""
    df["nombre_empresa"] = df["nombre_empresa"].fillna("").astype(str).str.strip()
    df["nit_empresa"] = normalizar_nit(df["nit_empresa"])
    df["nit_vinculado"] = normalizar_nit(df["nit_vinculado"])
    df["nombre_vinculado"] = df["nombre_vinculado"].fillna("").astype(str).str.strip()
    df["relacion"] = df["relacion"].fillna("").astype(str).str.strip().str.upper()
    # 'Estado' se ignora: en la fuente siempre es ACTIVO (no aporta diferenciación).

    if mapa_nit:  # compartir el espacio de NIT canónico con la capa transaccional
        df["nit_empresa"] = df["nit_empresa"].map(lambda n: mapa_nit.get(n, n))
        df["nit_vinculado"] = df["nit_vinculado"].map(lambda n: mapa_nit.get(n, n))

    df = df[(df["nit_empresa"] != "") & (df["nit_vinculado"] != "")].copy()
    LOG.info("Vinculados: %d relaciones normalizadas", len(df))
    return df


def normalizar_nombres_clientes(df_raw: pd.DataFrame, cfg: Config | None = None) -> pd.DataFrame:
    """Normaliza la tabla de nombres oficiales -> columnas [nit, nombre]."""
    if df_raw is None or not len(df_raw):
        return pd.DataFrame(columns=["nit", "nombre"])
    columnas = cfg.get("columnas_nombres", {"id": "nit", "nombre": "nombre"}) if cfg else {"id": "nit", "nombre": "nombre"}
    df = df_raw.rename(columns=columnas).copy()
    exigir({"nit", "nombre"}.issubset(df.columns), "La fuente de nombres requiere ID y nombre")
    df["nit"] = normalizar_nit(df["nit"])
    df["nombre"] = df["nombre"].fillna("").astype(str).str.strip()
    df = df[(df["nit"] != "") & (df["nombre"] != "")].drop_duplicates(subset="nit")
    return df[["nit", "nombre"]]
