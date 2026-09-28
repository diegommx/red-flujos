"""Ubicación y configuración del conjunto público de datos ficticios."""
from __future__ import annotations

from pathlib import Path

from .config import Config


DEMO_DIR = Path(__file__).with_name("demo_data")


def demo_config() -> Config:
    """Carga los CSV incluidos con el proyecto, sin acceder a fuentes externas."""
    cfg = Config.load()
    cfg.data["fuente"]["tipo"] = "csv"
    cfg.data["fuente"]["archivos"] = {
        "transacciones": str(DEMO_DIR / "flujos.csv"),
        "vinculados": str(DEMO_DIR / "relaciones.csv"),
        "nombres": str(DEMO_DIR / "nombres.csv"),
    }
    cfg.data["reconciliacion"]["modo"] = "espejo"
    return cfg
