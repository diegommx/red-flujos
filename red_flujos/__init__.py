"""Motor de análisis de redes de flujos y relaciones.

Uso mínimo:

    from red_flujos import Config, analizar
    resultado = analizar(Config.load())          # ejemplo sintético público
    print(resultado.resumen_nodos.head())
"""
from .config import Config
from .pipeline import Resultado, analizar

__all__ = ["Config", "analizar", "Resultado"]
