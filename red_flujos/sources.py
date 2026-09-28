"""Fuentes de datos seleccionadas explícitamente por quien ejecuta el análisis.

El paquete no incluye consultas, direcciones de servidores ni datos privados.
Cada fuente devuelve las columnas declaradas en la configuración del caso.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from io import BytesIO
import os

import numpy as np
import pandas as pd

from .config import Config
from .validation import LOG

class DataSource(ABC):
    @abstractmethod
    def fetch_transacciones(self) -> pd.DataFrame: ...

    @abstractmethod
    def fetch_vinculados(self) -> pd.DataFrame: ...

    def fetch_nombres_clientes(self) -> pd.DataFrame:
        """Nombres opcionales; una tabla vacía no impide analizar los flujos."""
        return pd.DataFrame()


# ---------------------------------------------------------------------------
class SqlSource(DataSource):
    """SQL Server con consultas proporcionadas en una configuración privada.

    Las consultas y sus parámetros son responsabilidad del usuario. No se
    interpolan identificadores ni valores en SQL dentro de la biblioteca.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg["fuente"]["sql"]
        self.queries = self.cfg.get("queries", {})
        self.params = self.cfg.get("params", {})
        if not self.cfg.get("server"):
            raise ValueError("La fuente SQL requiere 'fuente.sql.server' en un YAML privado")
        if not str(self.queries.get("transacciones", "")).strip():
            raise ValueError("La fuente SQL requiere una consulta de transacciones")

    def _conn(self):
        import pyodbc  # import diferido: solo se necesita en modo sql

        driver = self.cfg.get("driver", "ODBC Driver 18 for SQL Server")
        server = self.cfg["server"]
        database = self.cfg.get("database", "")
        cs = f"DRIVER={{{driver}}};SERVER={server};"
        if database:
            cs += f"DATABASE={database};"
        if self.cfg.get("trusted_connection", True):
            cs += "Trusted_Connection=yes;"
        else:
            uid = os.environ.get("RF_SQL_USER")
            pwd = os.environ.get("RF_SQL_PASSWORD")
            if not uid or not pwd:
                raise ValueError("Defina RF_SQL_USER y RF_SQL_PASSWORD en el entorno")
            cs += f"UID={uid};PWD={pwd};"
        return pyodbc.connect(cs)

    def _read(self, nombre: str) -> pd.DataFrame:
        query = str(self.queries.get(nombre, "")).strip()
        if not query:
            return pd.DataFrame()
        max_rows = int(self.cfg.get("max_rows", 100000))
        if max_rows <= 0:
            raise ValueError("fuente.sql.max_rows debe ser positivo")
        chunks = []
        n = 0
        with self._conn() as cn:
            for chunk in pd.read_sql_query(query, cn, params=self.params.get(nombre, []),
                                           chunksize=min(max_rows + 1, 10000)):
                n += len(chunk)
                if n > max_rows:
                    raise ValueError(f"La consulta {nombre} supera max_rows={max_rows}; acote su consulta")
                chunks.append(chunk)
        df = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
        LOG.info("SqlSource: %d filas recibidas para %s", len(df), nombre)
        return df

    def fetch_transacciones(self) -> pd.DataFrame:
        return self._read("transacciones")

    def fetch_vinculados(self) -> pd.DataFrame:
        return self._read("vinculados")

    def fetch_nombres_clientes(self) -> pd.DataFrame:
        return self._read("nombres")


# ---------------------------------------------------------------------------
class FileSource(DataSource):
    """CSV o Excel, desde rutas locales o bytes cargados por Streamlit."""

    def __init__(self, cfg: Config):
        self.cfg = cfg["fuente"].get("archivos", {})
        self.tipo = cfg["fuente"]["tipo"]

    def _read(self, nombre: str, required: bool = False) -> pd.DataFrame:
        archivo = self.cfg.get(nombre)
        if not archivo:
            if required:
                raise ValueError(f"Seleccione un archivo de {nombre}")
            return pd.DataFrame()
        entrada = BytesIO(archivo) if isinstance(archivo, bytes) else archivo
        if self.tipo == "csv":
            return pd.read_csv(entrada, dtype=str, encoding="utf-8-sig")
        hoja = self.cfg.get(f"hoja_{nombre}", 0)
        return pd.read_excel(entrada, sheet_name=hoja, dtype=str)

    def fetch_transacciones(self) -> pd.DataFrame:
        return self._read("transacciones", required=True)

    def fetch_vinculados(self) -> pd.DataFrame:
        return self._read("vinculados")

    def fetch_nombres_clientes(self) -> pd.DataFrame:
        return self._read("nombres")


# ---------------------------------------------------------------------------
class SyntheticSource(DataSource):
    """Genera datos ficticios con el esquema público de ejemplo.

    Incluye a propósito: flujos internos entre actores monitoreados (con su
    par espejo débito/crédito), contrapartes externas, contrapartes vacías,
    una variante de ID por prefijo, tipos de evento sin mapear, un relacionado
    compartido por varias empresas y algún vínculo inactivo.
    """

    def __init__(self, seed: int = 7, n_externas: int = 900, n_internas: int = 220):
        self.rng = np.random.default_rng(seed)
        self.n_externas = n_externas
        self.n_internas = n_internas
        self._preparar_actores()

    # -- catálogo de actores monitoreados -------------------------------------
    def _preparar_actores(self):
        pj = {
            "EMP-001": "EMPRESA DEMO 001 SAS",
            "EMP-002": "EMPRESA DEMO 002 SAS",
            "EMP-003": "EMPRESA DEMO 003 SAS",
            "EMP-004": "EMPRESA DEMO 004 SAS",
            "EMP-005": "EMPRESA DEMO 005 SAS",
            "EMP-006": "EMPRESA DEMO 006 SAS",
        }
        pn = {
            "PER-001": "PERSONA DEMO 001",
            "PER-002": "PERSONA DEMO 002",
            "PER-003": "PERSONA DEMO 003",
            "PER-004": "PERSONA DEMO 004",
            "PER-005": "PERSONA DEMO 005",
            "PER-006": "PERSONA DEMO 006",
        }
        self.pj, self.pn = pj, pn
        self.nombres = {**pj, **pn}
        self.monitoreados = list(self.nombres)

        # Externos con nombre
        self.externos = {
            f"EXT-{i:04d}": nom
            for i, nom in enumerate(
                [
                    "ENTIDAD EXTERNA 001",
                    "ENTIDAD EXTERNA 002",
                    "ENTIDAD EXTERNA 003",
                    "ENTIDAD EXTERNA 004",
                    "ENTIDAD EXTERNA 005",
                    "PERSONA EXTERNA 001",
                    "PERSONA EXTERNA 002",
                    "ENTIDAD EXTERNA 006",
                ],
                start=1,
            )
        }
        self.canales = [
            "ACH", "ATM No Propios", "CORRESPONSALES", "Dispositivos Moviles",
            "Internet", "Oficinas", "POS No Propios", "Pagos Automaticos",
        ]

    def _tipo(self, nit: str) -> str:
        return "JURIDICA" if nit in self.pj else "NATURAL"

    def _fecha(self):
        dia = int(self.rng.integers(1, 181))  # ~6 meses
        return pd.Timestamp("2025-01-01") + pd.Timedelta(days=dia)

    def _nombretx_debito(self):
        # Etiquetas genéricas de salida (Transaccion = RETIRO)
        return self.rng.choice(
            ["Retiro en efectivo", "Transferencia electrónica", "Pago móvil",
             "Pago QR", "Retiro en cajero", "Compra con tarjeta",
             "Transferencia web", "Pago con tarjeta"]
        )

    def _nombretx_credito(self):
        # Etiquetas genéricas de entrada (Transaccion = CONSIGNACION)
        return self.rng.choice(
            ["Depósito en efectivo", "Transferencia recibida", "Cobro QR",
             "Pago electrónico recibido", "Abono periódico", "Abono web"]
        )

    def _nombretx_prodcreditos(self):
        # Eventos deliberadamente fuera del mapeo para probar descartes.
        return self.rng.choice(
            ["Evento sin mapear A", "Evento sin mapear B", "Evento sin mapear C"]
        )

    # -- transacciones --------------------------------------------------------
    def fetch_transacciones(self) -> pd.DataFrame:
        filas = []
        _id = 1

        def fila(nit, canal, tx, nombretx, valor, fecha, ncp, nomcp):
            nonlocal _id
            filas.append(
                {
                    "id_evento": _id,
                    "actor": nit,
                    "contraparte": ncp,
                    "fecha": fecha,
                    "cantidad": valor,
                    "tipo_evento": tx,
                    "canal": canal,
                    "modalidad": nombretx,
                    "tipo_actor": self._tipo(nit),
                    "nombre_contraparte": nomcp,
                }
            )
            _id += 1

        # Flujos INTERNOS entre monitoreados (par espejo débito/crédito)
        for _ in range(self.n_internas):
            a, b = self.rng.choice(self.monitoreados, size=2, replace=False)
            valor = float(self.rng.integers(2, 400)) * 1_000_000
            fecha = self._fecha()
            canal = self.rng.choice(self.canales)
            fila(a, canal, "RETIRO", "Transferencia entre actores", valor, fecha, b, self.nombres[b])
            fila(b, canal, "CONSIGNACION", "Transferencia entre actores", valor, fecha, a, self.nombres[a])

        # Flujos EXTERNOS (un solo lado)
        for _ in range(self.n_externas):
            a = self.rng.choice(self.monitoreados)
            valor = float(self.rng.integers(1, 250)) * 1_000_000
            fecha = self._fecha()
            canal = self.rng.choice(self.canales)
            if self.rng.random() < 0.6:  # salida
                x = self.rng.choice(list(self.externos))
                fila(a, canal, "RETIRO", self._nombretx_debito(), valor, fecha, x, self.externos[x])
            else:  # entrada
                x = self.rng.choice(list(self.externos))
                fila(a, canal, "CONSIGNACION", self._nombretx_credito(), valor, fecha, x, self.externos[x])

        # Contrapartes vacías -> SIN_CONTRAPARTE
        for _ in range(40):
            a = self.rng.choice(self.monitoreados)
            fila(a, "ATM No Propios", "RETIRO", "Retiro en cajero",
                 float(self.rng.integers(1, 30)) * 1_000_000, self._fecha(), "", "")

        # Variante de identificador por prefijo para probar homologación optativa.
        fila("PER-001", "ACH", "RETIRO", "Transferencia electrónica", 55_000_000, self._fecha(),
             "EMP-00", "EMPRESA DEMO 001 SAS")

        # PROD-CREDITOS (pagos de crédito) -> deben EXCLUIRSE, con reporte
        for _ in range(120):
            a = self.rng.choice(self.monitoreados)
            fila(a, self.rng.choice(["CORRESPONSALES", "Dispositivos Moviles", "ACH"]),
                 "PROD-CREDITOS", self._nombretx_prodcreditos(),
                 float(self.rng.integers(1, 20)) * 1_000_000, self._fecha(), "", "")

        # Registros con Transaccion vacía y Canal NULL -> deben EXCLUIRSE
        for _ in range(25):
            a = self.rng.choice(self.monitoreados)
            fila(a, "NULL", "", "Evento sin categoría",
                 float(self.rng.integers(1, 15)) * 1_000_000, self._fecha(), "", "")

        df = pd.DataFrame(filas)
        df["cantidad"] = df["cantidad"].astype(str)
        df["fecha"] = df["fecha"].astype(str)
        LOG.info("SyntheticSource: %d transacciones generadas", len(df))
        return df

    # -- vinculados -----------------------------------------------------------
    def fetch_vinculados(self) -> pd.DataFrame:
        filas = []

        def fila(emp, dcto, nom, rel, estado="ACTIVO", ciiu="4711"):
            filas.append(
                {
                    "entidad": emp,
                    "nombre_entidad": self.pj.get(emp, ""),
                    "relacionado": dcto,
                    "nombre_relacionado": nom,
                    "tipo_relacion": rel,
                    "estado": estado,
                    "categoria": ciiu,
                }
            )

        # Contador COMPARTIDO por 3 empresas (hub -> bandera roja)
        contador_hub = ("VINC-001", "PERSONA VINCULADA DEMO")
        for emp in ["EMP-001", "EMP-002", "EMP-003"]:
            fila(emp, *contador_hub, "CONTADOR")

        # Representantes legales
        fila("EMP-001", "PER-001", "PERSONA DEMO 001", "REPRESENTANTE LEGAL")
        fila("EMP-002", "PER-001", "PERSONA DEMO 001", "REPRESENTANTE LEGAL")
        fila("EMP-003", "PER-003", "PERSONA DEMO 003", "REPRESENTANTE LEGAL")
        fila("EMP-004", "PER-002", "PERSONA DEMO 002", "REPRESENTANTE LEGAL")
        fila("EMP-005", "PER-006", "PERSONA DEMO 006", "REPRESENTANTE LEGAL")
        fila("EMP-006", "PER-005", "PERSONA DEMO 005", "REPRESENTANTE LEGAL")

        # Socios (algunos son PJ -> vínculo empresa-empresa)
        fila("EMP-001", "EMP-003", "EMPRESA DEMO 003 SAS", "SOCIO", ciiu="4923")
        fila("EMP-001", "PER-002", "PERSONA DEMO 002", "SOCIO")
        fila("EMP-002", "PER-003", "PERSONA DEMO 003", "SOCIO")
        fila("EMP-004", "PER-001", "PERSONA DEMO 001", "SOCIO")
        fila("EMP-005", "PER-005", "PERSONA DEMO 005", "SOCIO")

        # Revisor fiscal ficticio
        fila("EMP-006", "VINC-002", "ENTIDAD VINCULADA DEMO", "REVISOR FISCAL", ciiu="6920")

        df = pd.DataFrame(filas)
        LOG.info("SyntheticSource: %d vínculos generados", len(df))
        return df

    def fetch_nombres_clientes(self) -> pd.DataFrame:
        """Nombres formales ficticios para verificar su precedencia."""
        filas = [{"id": nit, "nombre": nom.replace(" SAS", " S.A.S.")}
                 for nit, nom in self.pj.items()]
        filas.append({"id": "EMP-INEXISTENTE", "nombre": "EMPRESA FICTICIA NO OBSERVADA"})
        LOG.info("SyntheticSource: %d nombres oficiales generados", len(filas))
        return pd.DataFrame(filas)


# ---------------------------------------------------------------------------
def build_source(cfg: Config) -> DataSource:
    tipo = str(cfg["fuente"]["tipo"]).lower()
    if tipo == "sql":
        return SqlSource(cfg)
    if tipo in {"excel", "csv"}:
        return FileSource(cfg)
    if tipo == "synthetic":
        return SyntheticSource()
    raise ValueError(f"Tipo de fuente desconocido: {tipo}")
