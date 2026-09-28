# Datos ficticios para explorar la aplicación

Estos tres CSV se generaron con `scripts/generar_demo.py` y una semilla fija (19). Las entidades, personas e identificadores son inventados (`EMP-`, `PER-`, `EXT-` y `VINC-`). Los importes y fechas son aleatorios. No proceden de ninguna organización.

| Archivo | Contenido |
|---|---|
| `flujos.csv` | 456 observaciones, incluidos 45 pares espejo y 145 registros deliberadamente descartables. |
| `relaciones.csv` | 15 vínculos ficticios, entre ellos un relacionado compartido. |
| `nombres.csv` | 7 nombres ficticios de ejemplo. |

El botón **Explorar datos ficticios** de la aplicación carga una copia idéntica de estos archivos incluida dentro del paquete. Tras validar y reconciliar los pares espejo quedan **266 eventos** para explorar los filtros, grafos, ciclos y relaciones. Los tres archivos también pueden abrirse con la opción CSV para probar la carga manual; en ese caso active la reconciliación de registros espejo.

Para regenerarlos desde el código, ejecute `python scripts/generar_demo.py` desde la raíz del proyecto. No edite estos archivos con datos propios: guarde sus archivos reales fuera de esta carpeta y fuera del repositorio.
