# Contribuir

1. Cree un entorno Python 3.10 o superior e instale `pip install -e ".[dashboard,test]"`.
2. Ejecute `python -m pytest` y `red-flujos --source synthetic`.
3. Acompañe cambios de normalización, identidad, reconciliación o métricas con
   una prueba que muestre el comportamiento esperado y un caso adversario.
4. Use exclusivamente datos sintéticos en ejemplos, pruebas e issues.
5. Describa el significado de cantidades, unidades y dirección al añadir una
   nueva fuente o detector.
