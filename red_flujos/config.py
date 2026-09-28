"""Carga y acceso a la configuración del motor."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import copy

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.yaml")


@dataclass
class Config:
    """Envoltura ligera sobre el YAML de configuración."""

    data: dict[str, Any]
    ruta: Path | None = None

    # -- carga -----------------------------------------------------------------
    @classmethod
    def load(cls, path: str | Path | None = None) -> "Config":
        with open(DEFAULT_CONFIG_PATH, "r", encoding="utf-8") as fh:
            base = yaml.safe_load(fh)
        if not path:
            return cls(base, ruta=DEFAULT_CONFIG_PATH)
        p = Path(path)
        if p.resolve() == DEFAULT_CONFIG_PATH.resolve():
            return cls(base, ruta=p)
        with open(p, "r", encoding="utf-8") as fh:
            cambios = yaml.safe_load(fh) or {}
        if not isinstance(cambios, dict):
            raise ValueError("El YAML del caso debe contener un mapa de configuración")

        def fusionar(destino: dict, origen: dict) -> None:
            for clave, valor in origen.items():
                if isinstance(valor, dict) and isinstance(destino.get(clave), dict):
                    fusionar(destino[clave], valor)
                else:
                    destino[clave] = copy.deepcopy(valor)

        fusionar(base, cambios)
        return cls(base, ruta=p)

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    # -- accesos convenientes --------------------------------------------------
    @property
    def col_tx(self) -> dict[str, str]:
        return self.data["columnas_transaccional"]

    @property
    def col_vin(self) -> dict[str, str]:
        return self.data["columnas_vinculados"]

    @property
    def presentacion(self) -> dict[str, Any]:
        return self.data.get("presentacion", {})

    @property
    def reconciliacion(self) -> dict[str, Any]:
        return self.data.get("reconciliacion", {"modo": "auto"})

    @property
    def homologacion(self) -> dict[str, Any]:
        return self.data.get("homologacion", {"modo": "exacta"})

    @property
    def mapa_sentido(self) -> dict[str, str]:
        """{TRANSACCION_SIN_ACENTOS_MAYUS: DEBITO|CREDITO}."""
        import unicodedata

        def _norm(s: str) -> str:
            s = str(s).upper().strip()
            return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))

        return {_norm(k): str(v).upper() for k, v in self.data["transaccion"]["mapa_sentido"].items()}

    @property
    def juridica_valores(self) -> list[str]:
        return [str(v).upper() for v in self.data["tipo_persona"]["juridica_valores"]]

    @property
    def auto_detectar_clientes(self) -> bool:
        return bool(self.data["clientes"]["auto_detectar"])

    @property
    def clientes_manual(self) -> dict[str, str]:
        return dict(self.data["clientes"].get("manual", {}))

    @property
    def filtros(self) -> dict[str, Any]:
        return self.data["filtros"]

    @property
    def filtro_carga(self) -> dict[str, Any]:
        return self.data.get("filtro_carga", {})

    @property
    def unir_nits(self) -> dict[str, str]:
        return dict(self.homologacion.get("unir_nits", {}))

    @property
    def vinculados(self) -> dict[str, Any]:
        return self.data["vinculados"]

    @property
    def roles_control(self) -> list[str]:
        return [str(r).upper() for r in self.data["vinculados"]["roles_control"]]
