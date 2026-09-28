# Documentación técnica de red-flujos

Este documento describe el estado del código después de la primera evolución hacia un proyecto reutilizable. La [propuesta de evolución](PROPUESTA_EVOLUCION.md) contiene capacidades futuras que aún no están implementadas. El caso financiero sigue siendo el perfil funcional más completo.

## 1. Inicio y selección de fuente

En Windows, haga doble clic en [`INICIAR_RED_FLUJOS.cmd`](INICIAR_RED_FLUJOS.cmd) y pulse **Iniciar proyecto**. El iniciador gráfico crea `.venv` e instala `.[dashboard]` si falta, arranca Streamlit solo en `127.0.0.1` y abre el navegador. Su registro técnico queda en la carpeta local de aplicaciones del usuario, fuera del repositorio. El botón **Detener** cierra el proceso. También puede instalar con `pip install -e ".[dashboard]"` y abrir `streamlit run app.py` desde una terminal.

La primera pantalla ofrece **Explorar datos ficticios**, que carga los tres [CSV de demostración](examples/demo_financiero/README.md), o permite elegir **ejemplo sintético, CSV, Excel o SQL Server**. No se inicia ninguna consulta al abrir la app. El resultado se guarda en la sesión de Streamlit, separado de las demás sesiones; «Cambiar fuente de datos» descarta ese resultado y los alias.

La consola usa `red-flujos`: sin argumentos pregunta por la fuente; `red-flujos --source synthetic` permite ejecutar el ejemplo sin interacción. Para archivos se usan `--transactions`, `--relations`, `--names` y `--config`. La biblioteca Python no pregunta: `analizar(Config.load(...))` usa por defecto el ejemplo sintético o la configuración pasada explícitamente.

```python
from red_flujos import Config, analizar

resultado = analizar(Config.load())  # sólo datos sintéticos
print(resultado.resumen_nodos.head())
```

`red_flujos/config.yaml` es una base pública sin direcciones ni consultas. Un YAML adicional se fusiona con ella en `Config.load("mi_caso.local.yaml")`; puede redefinir fuente, columnas, reglas y presentación. Mantenga el YAML del caso fuera de Git. Un ejemplo genérico de SQL está en [`examples/sql.example.yaml`](examples/sql.example.yaml).

## 2. Flujo del motor

```text
fuente seleccionada
    -> normalización y reporte de descartes
    -> detección de actores observados
    -> homologación de identidad y reporte de decisiones
    -> dirección / reconciliación opcional de registros espejo
    -> grafo de flujos + grafo de relaciones
    -> métricas y tablas
    -> Resultado -> dashboard o CLI
```

| Archivo | Responsabilidad actual |
|---|---|
| [`sources.py`](red_flujos/sources.py) | Fuente sintética, archivos CSV/Excel y SQL parametrizado por el usuario. No contiene consultas privadas. |
| [`normalize.py`](red_flujos/normalize.py) | Mapeo de columnas, identificadores de texto, dirección, validación básica y extremos desconocidos por evento. |
| [`homologate.py`](red_flujos/homologate.py) | Fusión exacta o por prefijo con nombre, fusiones manuales y protección de actores monitoreados distintos. |
| [`dedup.py`](red_flujos/dedup.py) | Origen/destino y reconciliación conservadora de observaciones espejo. |
| [`graphs.py`](red_flujos/graphs.py) | Grafo dirigido agregado por par y grafo de relaciones. |
| [`analytics.py`](red_flujos/analytics.py) | Totales, canales, flujos internos, centralidad, ciclos y relaciones compartidas. |
| [`pipeline.py`](red_flujos/pipeline.py) | Orquestación y objeto `Resultado`. |
| [`app.py`](app.py), [`dashboard/`](red_flujos/dashboard/) | Selección de fuente y vistas Streamlit/Plotly/Pyvis. |
| [`launcher_core.py`](launcher_core.py), [`iniciar_red_flujos.pyw`](iniciar_red_flujos.pyw) | Instalación inicial y servidor local desde la ventana de Windows. No requieren librerías externas para mostrar la ventana. |
| [`demo.py`](red_flujos/demo.py), [`generar_demo.py`](scripts/generar_demo.py) | Carga y generación reproducible de los CSV ficticios. |

El motor no importa Streamlit. El dashboard es un cliente que aplica filtros sobre los eventos ya cargados y reconstruye el grafo de la vista.

## 3. Contrato de entrada de esta versión

El archivo de flujos necesita `actor`, `contraparte`, `fecha`, `cantidad`, `tipo_evento`, o bien otras columnas mapeadas a los nombres internos `nit`, `nit_contraparte`, `fecha_str`, `valor`, `transaccion`. `id_evento`, `canal`, `modalidad`, `tipo_actor` y `nombre_contraparte` son opcionales. Si faltan, se completan con valores vacíos. La fecha debe ser interpretable por pandas y la cantidad debe ser positiva.

`transaccion.mapa_sentido` define la dirección. El tipo `DEBITO` significa `actor -> contraparte`; `CREDITO`, `contraparte -> actor`. Valores sin regla se excluyen e informan. El ejemplo financiero usa RETIRO y CONSIGNACION; el ejemplo logístico usa FLUJO como débito. Las etiquetas y unidades se definen en `presentacion` y pueden mostrar COP, kg, bytes u otra cantidad. No se mezclan unidades dentro de un mismo análisis.

Los identificadores se mantienen como texto. En CSV se leen con `dtype=str`; en Excel, configure las columnas de ID como texto antes de exportar para preservar ceros iniciales. Si una fuente entrega un número de punto flotante demasiado grande o fraccional como ID, se detiene el proceso para evitar una identidad inventada. Los extremos vacíos reciben un ID distinto por evento. Sólo en el grafo visible se agrupan bajo «Sin contraparte».

El archivo de relaciones es opcional. Si existe, requiere `entidad`, `relacionado`, `tipo_relacion`, mapeados internamente a `nit_empresa`, `nit_vinculado`, `relacion`. Nombres, estado y categoría son opcionales. La tabla opcional de nombres usa `id` y `nombre`.

## 4. Configuración y seguridad de datos

| Sección | Claves importantes | Uso |
|---|---|---|
| `fuente` | `tipo`, `archivos`, `sql` | La interfaz establece el tipo al confirmar. SQL requiere un YAML privado. |
| `columnas_transaccional`, `columnas_vinculados`, `columnas_nombres` | columna de origen -> columna interna | Adaptar un esquema sin cambiar el código. |
| `transaccion` | `mapa_sentido` | Dirección de los eventos; lo no mapeado se excluye. |
| `homologacion` | `modo`, `unir_nits` | `exacta` es la opción por defecto; `prefijo` exige mismo nombre normalizado. |
| `reconciliacion` | `modo` | `auto` reconcilia sólo el ejemplo sintético; `espejo` para observaciones de ambos lados; `ninguna` para eventos únicos. |
| `clientes` | `auto_detectar`, `manual` | Actores monitoreados a partir del campo `actor`, o lista manual. |
| `presentacion` | `identificador`, `cantidad`, `unidad`, `escala`, `simbolo`, `relaciones` | Términos y formatos de las vistas. |
| `vinculados` | `umbral_hub` | Número de entidades compartidas que marca un hub de relaciones. |

`SqlSource` lee el servidor, base, driver, consultas y parámetros del YAML del usuario. La consulta de flujos es obligatoria; relaciones y nombres son opcionales. Los valores de `params` se pasan a `pd.read_sql_query` como parámetros, sin interpolarlos en el código. La consulta debe acotar sus filas según el caso; no existe un filtro corporativo implícito. Para autenticación SQL, las credenciales proceden exclusivamente de `RF_SQL_USER` y `RF_SQL_PASSWORD`. Los errores detallados de conexión no se muestran en el dashboard.

Los archivos cargados por Streamlit y los resultados permanecen en memoria de la sesión. Los alias no se escriben en `red_flujos/`. La descarga CSV es una acción explícita del usuario. La app no ofrece autenticación ni controles para alojarla como servicio compartido con datos sensibles.

## 5. Exactitud de identidad, reconciliación y grafos

La homologación `exacta` reúne registros del mismo ID. `prefijo` considera IDs compatibles sólo con nombres normalizados iguales. Un componente que incluya dos actores monitoreados distintos se rechaza o se informa como conflicto; no se fusionan silenciosamente. Las decisiones automáticas y manuales están en `Resultado.reportes["homologacion"]`. Las reglas actuales son deterministas y conservadoras, pero no sustituyen una revisión de identidad cuando la fuente sea ambigua.

La reconciliación distingue copias de un mismo registro con el mismo `id_evento` del emparejamiento de débito y crédito. En modo espejo sólo se elimina el crédito si hay un único débito y un único crédito con igual origen, destino, instante, cantidad y canal. Grupos múltiples se conservan y se cuentan en `Resultado.reportes["dedup"]`. Si la fuente sólo tiene fecha sin hora, la precisión de la reconciliación será menor; el analista debe elegir `ninguna` si no puede sostener esa equivalencia.

`G_col` agrega eventos por par origen-destino; `G_principal` aplica filtros de nodos; `G_topologia` excluye extremos sin identificar para ciclos y centralidad. `G_estructura` almacena relaciones tipadas. PageRank usa la cantidad agregada como intensidad. Betweenness usa número de saltos: en NetworkX un peso numérico de betweenness es una **distancia**, por lo que usar el importe directamente cambiaría el significado de la métrica.

Los ciclos calculados son topológicos en el grafo agregado. La versión actual aún no verifica el orden temporal de los eventos ni la vigencia temporal de las relaciones.

## 6. Objeto `Resultado`

`analizar(cfg)` devuelve `Resultado` con `df_tx` (eventos normalizados y reconciliados), `df_vin`, grafos, `resumen_nodos`, `metricas`, `ciclos`, `flujos_actores`, `canal_actor`, `hubs`, `pares_estructura`, `mapa_nombre`, `reportes` y `presentacion`. Los nombres internos conservan algunas palabras del caso financiero para compatibilidad inicial; la interfaz externa usa el mapeo y la presentación configurados.

El dashboard filtra fechas, dirección, cantidad, canales y actores; muestra resumen, red, Sankey, heatmaps, relaciones y tabla de datos. La vista de relaciones depende de la fuente de relaciones, no de los filtros de eventos. La disposición manual de nodos vive en el navegador y se pierde al cambiar filtros.

## 7. Desarrollo y límites

Use `pip install -e ".[dashboard,test]"`, `python -m pytest` y `red-flujos --source synthetic`. La CI ejecuta pruebas, compilación y demo sintético en varias versiones de Python. No se necesitan datos privados para estas comprobaciones.

Quedan para etapas posteriores el contrato neutral de eventos versionado, la resolución de identidad con revisión humana, detectores temporales, un sistema de perfiles instalables, benchmarks grandes y un servicio multiusuario con permisos. La [propuesta](PROPUESTA_EVOLUCION.md) detalla su secuencia y criterios.
