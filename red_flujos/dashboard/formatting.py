"""Presentación de cantidades e identificadores según el caso analizado."""
from __future__ import annotations


def cantidad(valor: float, presentacion: dict | None = None) -> str:
    p = presentacion or {}
    escala = float(p.get("escala", 1) or 1)
    precision = int(p.get("precision", 1))
    simbolo = str(p.get("simbolo", ""))
    sufijo = str(p.get("sufijo_escala", ""))
    unidad = str(p.get("unidad", ""))
    return f"{simbolo}{valor / escala:,.{precision}f}{sufijo}" + (f" {unidad}" if unidad and not simbolo else "")


def unidad_eje(presentacion: dict | None = None) -> str:
    p = presentacion or {}
    simbolo = str(p.get("simbolo", ""))
    sufijo = str(p.get("sufijo_escala", ""))
    unidad = str(p.get("unidad", ""))
    return f"{simbolo}{sufijo}" + (f" {unidad}" if unidad and not simbolo else "")
