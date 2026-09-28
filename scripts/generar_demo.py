"""Regenera los CSV públicos a partir de identificadores y nombres inventados."""
from __future__ import annotations

from pathlib import Path

from red_flujos.sources import SyntheticSource


DESTINO = Path(__file__).resolve().parents[1] / "examples" / "demo_financiero"
PAQUETE = Path(__file__).resolve().parents[1] / "red_flujos" / "demo_data"


def main() -> None:
    fuente = SyntheticSource(seed=19, n_externas=180, n_internas=45)
    DESTINO.mkdir(parents=True, exist_ok=True)
    PAQUETE.mkdir(parents=True, exist_ok=True)
    for nombre, tabla in (
        ("flujos.csv", fuente.fetch_transacciones()),
        ("relaciones.csv", fuente.fetch_vinculados()),
        ("nombres.csv", fuente.fetch_nombres_clientes()),
    ):
        for carpeta in (DESTINO, PAQUETE):
            tabla.to_csv(carpeta / nombre, index=False, encoding="utf-8")


if __name__ == "__main__":
    main()
