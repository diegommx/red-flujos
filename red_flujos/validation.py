"""Logging estructurado y validaciones formalizadas.

Reemplaza los ``print`` de validación del notebook por registros con nivel y
por *checks* que dejan traza sin abortar el pipeline (salvo errores duros).
"""
from __future__ import annotations

import logging
from contextlib import contextmanager

_FMT = "%(asctime)s  %(levelname)-7s  %(name)s  %(message)s"


def get_logger(nombre: str = "red_flujos", nivel: str = "INFO") -> logging.Logger:
    logger = logging.getLogger(nombre)
    if not logger.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter(_FMT, datefmt="%H:%M:%S"))
        logger.addHandler(h)
    logger.setLevel(getattr(logging, str(nivel).upper(), logging.INFO))
    logger.propagate = False
    return logger


LOG = get_logger()


@contextmanager
def etapa(titulo: str):
    """Marca inicio/fin de una etapa del pipeline en el log."""
    LOG.info("=" * 60)
    LOG.info("ETAPA: %s", titulo)
    LOG.info("=" * 60)
    yield
    # el detalle de cada etapa lo emite la propia función


class ErrorValidacion(Exception):
    """Se lanza cuando una precondición dura del pipeline no se cumple."""


def exigir(condicion: bool, mensaje: str) -> None:
    """Check duro: si falla, detiene el pipeline con un mensaje claro."""
    if not condicion:
        raise ErrorValidacion(mensaje)


def advertir_si(condicion: bool, mensaje: str) -> None:
    """Check blando: registra una advertencia pero deja continuar."""
    if condicion:
        LOG.warning(mensaje)
