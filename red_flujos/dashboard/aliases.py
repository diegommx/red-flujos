"""Selección de entidades sin nombre para alias aislados por sesión."""
from __future__ import annotations

from ..normalize import es_desconocido

def sin_nombre(res, mapa_actual: dict[str, str], top: int = 200) -> list[str]:
    """IDs del universo cargado cuyo nombre efectivo está vacío o es el ID.

    Ordenados por monto (los más relevantes primero), actores incluidos.
    """
    rn = res.resumen_nodos.head(top)
    out = []
    for nit in list(res.clientes) + rn["nit"].tolist():
        if nit in out or es_desconocido(nit):
            continue
        nom = (mapa_actual.get(nit) or "").strip()
        if not nom or nom == nit:
            out.append(nit)
    return out
