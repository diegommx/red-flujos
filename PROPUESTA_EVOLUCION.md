# Propuesta de evolución: de red de flujos financieros a plataforma de análisis de redes de eventos

> Documento de trabajo, 26 de septiembre de 2026. Se basa en la lectura de `DOCUMENTACION.md`, `README.md`, `app.py` y el código de `red_flujos/`. Describe una dirección de producto y una secuencia de implementación; las capacidades futuras aquí propuestas aún no existen.

> **Actualización, 27 de septiembre de 2026:** el apartado 2 refleja el diagnóstico previo a la primera evolución. La selección explícita de fuente, la limpieza de referencias corporativas, el manejo de identificadores, la reconciliación conservadora, la centralidad y el aislamiento de sesión se implementaron después de ese diagnóstico. El estado ejecutable se describe en [DOCUMENTACION.md](DOCUMENTACION.md).

## 1. Visión

Convertir `red_flujos` en una herramienta abierta para investigar **quién intercambia qué, con quién, cuándo y a través de qué medio**, y cómo las relaciones entre entidades ayudan a explicar esos intercambios. El caso financiero actual sería el primer perfil de dominio, acompañado después por perfiles de ciberseguridad, logística, contratación pública y colaboración organizacional.

La unidad básica sería un **evento dirigido y fechado**, con una cantidad y su unidad explícita. Una segunda capa almacenaría relaciones entre entidades, también con tipo y vigencia. Sobre ambas capas, el usuario podría reconstruir el origen de cada resultado, filtrar, comparar períodos y examinar hallazgos explicables. Un hub o un ciclo sería una señal para investigar, nunca una conclusión automática de fraude, intrusión o mala conducta.

**Propuesta de valor:** un motor local que una datos heterogéneos, conserve trazabilidad de las transformaciones y produzca análisis de redes reproducibles, sin obligar a usar una base de grafos ni a desplegar una infraestructura compleja para comenzar.

## 2. Punto de partida verificado

El proyecto ya tiene una separación útil entre motor y dashboard. El motor carga datos desde SQL Server, Excel o una fuente sintética; normaliza movimientos bancarios; homologa NIT; elimina registros espejo débito/crédito; construye grafos de flujo y vínculos societarios; calcula resúmenes, centralidad y ciclos cortos. Streamlit ofrece filtros, red interactiva, Sankey, heatmaps, estructura societaria y descarga CSV.

La tabla siguiente distingue capacidades observadas de cambios necesarios. Es un diagnóstico del código actual, no una lista de defectos de datos reales:

| Prioridad | Hallazgo en el código | Consecuencia para una versión pública o multisectorial |
|---|---|---|
| Crítica | [`config.yaml`](red_flujos/config.yaml) selecciona SQL por defecto y contiene un nombre de servidor e identificadores de un caso concreto. [`README.md`](README.md) presenta el demo como sintético aunque `run_demo.py` carga ese YAML. | Sustituir por configuración de ejemplo ficticia y hacer que el primer uso funcione sin acceso corporativo. Revisar también derechos sobre consultas, esquemas y ejemplos antes de publicar. |
| Crítica | [`normalizar_nit()`](red_flujos/normalize.py) pasa los identificadores por `pd.to_numeric` y después a entero. | Pierde ceros iniciales y no admite IP, UUID, códigos de bodega o usuarios. También puede alterar identificadores numéricos largos por precisión. |
| Alta | [`deduplicar()`](red_flujos/dedup.py) empareja por día, importe y par de NIT sin identificador compartido de operación. | Movimientos legítimos del mismo valor y día pueden confundirse; dos direcciones entre el mismo par requieren reconciliación explícita. La regla sólo tiene sentido para determinadas fuentes bancarias. |
| Alta | [`homologar()`](red_flujos/homologate.py) usa coincidencias y prefijos de NIT/nombre, con fusiones por componentes conectados. | Una unión errónea puede propagarse a otros registros. Hace falta evidencia de la decisión, revisión de ambigüedades y protección ante fusiones de dos actores monitoreados distintos. |
| Alta | [`metricas_centralidad()`](red_flujos/analytics.py) pasa `total` como peso de `betweenness_centrality`. | NetworkX interpreta ese peso como **distancia**; así, un flujo mayor equivale a un camino más largo. Hay que definir si se quiere centralidad sin peso, por coste real o por una distancia derivada de intensidad. [Referencia de NetworkX](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.centrality.betweenness_centrality.html). |
| Alta | `SIN_CONTRAPARTE` representa múltiples extremos desconocidos como un nodo único; el código ya lo excluye de centralidad y ciclos. | La decisión evita algunos artefactos, pero aún impide distinguir eventos y patrones temporales por contraparte desconocida. En el modelo general deben conservarse los extremos desconocidos sin inventar una identidad común. |
| Alta | [`app.py`](app.py) usa `st.cache_resource` para el resultado completo y [`aliases.py`](red_flujos/dashboard/aliases.py) guarda nombres en un JSON dentro del paquete. | Al evolucionar a varios usuarios o casos se necesita aislamiento de resultados y anotaciones. La caché global de Streamlit se comparte entre usuarios y sesiones según su [documentación](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_resource). |
| Media | La interfaz y varias analíticas fijan NIT, pesos monetarios, `$M`, `PN/PJ`, RETIRO/CONSIGNACIÓN y vínculos societarios. | Separar etiquetas, unidades, dirección y detectores propios del dominio de las operaciones generales sobre grafos. |
| Media | No hay `pyproject.toml`, licencia, pruebas, CI ni metadatos de distribución visibles en esta carpeta. Tampoco hay repositorio Git inicializado aquí. | Preparar un paquete instalable y una publicación reproducible antes de invitar a otros a contribuir. |

**Límite de esta revisión:** se inspeccionó el código, pero no se ejecutó el pipeline: el intérprete disponible no tiene instalada la dependencia `PyYAML`. No se ha comprobado una conexión SQL ni la calidad de datos corporativos.

## 3. Principios de diseño

1. **El evento original permanece identificable.** Cada agregación, arista y hallazgo debe poder remontarse a registros de entrada concretos.
2. **Identidad, evento y relación son objetos distintos.** Dos observaciones parecidas no se convierten automáticamente en la misma entidad ni en el mismo evento.
3. **La unidad importa.** COP, bytes, kilogramos e interacciones no se suman entre sí. Las conversiones deben ser declaradas y reproducibles.
4. **El tiempo importa.** El grafo agregado sirve para exploración; patrones como exfiltración, rutas, ciclos y movimiento lateral requieren secuencia temporal.
5. **El dominio define el significado.** Una devolución logística, una respuesta DNS y una consignación no comparten reglas de deduplicación ni umbrales de alerta.
6. **Las señales muestran evidencia y límites.** Cada detector publica entradas, ventana, regla, versión, filas que lo sustentan y razones que podrían explicar un falso positivo.
7. **Uso local primero.** CSV/Parquet y Python bastan para la primera versión pública. API, base de grafos y despliegue multiusuario se añadirían al demostrar la necesidad.

## 4. Modelo de datos propuesto

### 4.1 Capas

```text
Fuente original -> observaciones validadas -> entidades y eventos canónicos
                                      |                  |
                                      |                  +-> vistas de grafos por ventana/filtro
                                      +-> reporte de calidad y procedencia
                                                            |
                                                     detectores y evidencias
                                                            |
                                                  CLI / Python / dashboard / API
```

| Objeto | Campos mínimos propuestos | Reglas |
|---|---|---|
| `Entidad` | `entity_id`, `namespace`, `external_id`, `entity_type`, `display_name` | `entity_id` es opaco; el par `namespace + external_id` evita colisiones entre sistemas. IP, NIT y usuario se conservan como texto. |
| `EventoFlujo` | `event_id`, `source_id`, `origin_id`, `destination_id`, `event_time`, `observed_at`, `quantity`, `unit`, `channel`, `modality`, `attributes`, `raw_ref` | El valor es no negativo, con precisión definida por el perfil. El sentido se resuelve antes de agregar. Conservar zona horaria y calidad de la fecha. |
| `RelacionEntidad` | `relation_id`, `subject_id`, `object_id`, `relation_type`, `valid_from`, `valid_to`, `source_id`, `raw_ref` | Puede ser dirigida o no, y tener múltiples tipos entre el mismo par. Su vigencia limita los cruces con eventos. |
| `DecisionIdentidad` | observaciones vinculadas, entidad canónica, método, evidencia, confianza, revisor, versión | Las fusiones automáticas deben poder deshacerse y auditarse. |
| `Hallazgo` | `finding_id`, detector/versión, entidades, ventana, métricas, umbral, referencias de eventos, estado de revisión | Es una hipótesis explicable, no una etiqueta de culpabilidad. |

**Extremos faltantes:** marcar `origin_id` o `destination_id` como desconocido en cada evento; si se necesita visualizar un agregado, usar un nodo virtual sólo en esa vista. No convertir todos los desconocidos en una persona, IP o empresa ficticia.

**Reconciliación:** distinguir tres operaciones: eliminar duplicados exactos de ingesta (`source_id + event_id`), reconciliar dos observaciones de un mismo evento si existe una referencia confiable, y agregar eventos independientes entre dos entidades. Si no hay una clave de enlace suficientemente fuerte, conservar ambos registros y reportar la incertidumbre. La lógica débito/crédito actual quedaría encapsulada en el perfil financiero, con pruebas de colisiones.

**Compatibilidad:** conservar temporalmente `analizar(Config.load(...))` y `Resultado` como fachada del perfil financiero. La migración al nuevo contrato se haría con adaptadores y avisos de deprecación, evitando romper de golpe a los usuarios iniciales.

### 4.2 Perfiles de dominio

Un perfil declararía el mapeo de columnas, el tipo y la unidad de cantidad, el tratamiento de extremos faltantes, la regla de sentido, las relaciones válidas, los detectores disponibles y las etiquetas de la interfaz. El conector sólo lee datos; el perfil les da significado.

Ejemplo **conceptual** de configuración futura (esta sintaxis aún no está implementada):

```yaml
profile: cybersecurity
sources:
  flows:
    format: parquet
    path: data/flows.parquet
mapping:
  event_id: flow_id
  origin: src_ip
  destination: dst_ip
  event_time: start_time
  quantity: bytes_out
  channel: protocol
quantity:
  unit: byte
  aggregation: sum
identity:
  namespace: ip
detectors:
  - receiver_concentration
  - internal_lateral_movement
```

La configuración de un **caso** (rutas, credenciales, filtros, anotaciones) viviría fuera del paquete y fuera del repositorio público. Los perfiles versionados y los datos sintéticos sí formarían parte del repositorio.

## 5. Aplicaciones por sector

| Perfil | Primer conjunto de datos de demostración | Detectores iniciales | Precaución de interpretación |
|---|---|---|---|
| Finanzas y LA/FT | Movimientos y vinculados sintéticos basados en el caso actual. | Concentración de recepción, ciclos temporales, flujos entre monitoreados, estructura compartida. | Monto agregado y ciclo topológico por sí solos no prueban lavado; revisar moneda, observaciones espejo y vigencia societaria. |
| SOC / SIEM | NetFlow o registros de firewall sintéticos, con inventario de activos. | Destinos externos receptores de alto volumen frente a línea base, secuencias internas entre activos, comunicación periódica. | NAT, DHCP, IP compartidas y protocolos cambian la identidad de los nodos; bytes enviados y recibidos deben distinguirse. |
| Logística | Guías sintéticas con bodega, trayecto, hora y peso. | Saturación por capacidad, rutas repetidas, devoluciones, impacto de retirar un nodo o tramo. | Una ruta circular puede ser normal; usar tiempos de tránsito, capacidad y estados de entrega. |
| Contratación y subsidios | Contratos/pagos y representantes ficticios o datos públicos cuya reutilización esté verificada. | Contratistas que comparten vinculados, pagos posteriores entre adjudicatarios, concentración por entidad y período. | Diferenciar adjudicación, obligación y desembolso; un representante común es una conexión, no una irregularidad. |
| ONA | Metadatos sintéticos de tickets, commits o mensajes, sin contenido privado. | Dependencia de un aprobador, concentración de coordinación, puentes entre equipos y cambios por período. | Frecuencia de interacción no equivale a desempeño; limitar reidentificación, acceso y usos de evaluación individual. |

**Secuencia recomendada:** publicar primero el perfil financiero sintético, luego demostrar que el núcleo soporta **dos perfiles muy distintos** (ciberseguridad y logística). Contratación y ONA entrarían cuando la procedencia, la vigencia de relaciones y el control de acceso estén resueltos.

## 6. Capacidades ambiciosas a construir

### 6.1 Ingesta y calidad

- CSV, Excel y Parquet como entradas locales; SQL Server como complemento opcional. Más adelante, conectores documentados para otras bases o APIs, sujetos a permisos y formatos reales.
- Contratos de esquema versionados: columnas obligatorias, tipos, zona horaria, unidades, unicidad, rangos y valores desconocidos. Las filas inválidas deben ir a un reporte de rechazo con causa y referencia original.
- Perfilado antes del análisis: cobertura de identificadores, fechas y cantidades; distribución por canal; duplicados; tasas de descarte; cambios frente a una ejecución anterior.
- Manifiesto de ejecución con versión de código, perfil, parámetros, huellas de los archivos de entrada y conteos de cada etapa. Permitir repetir un análisis con las mismas entradas.

### 6.2 Identidad y reconciliación

- Resolución determinista por identificador exacto y namespace como primer nivel. Candidatos difusos por nombre o prefijo sólo con evidencia visible y umbrales configurables.
- Cola de revisión para fusiones dudosas: aceptar, rechazar, separar entidades y registrar quién tomó la decisión. Medir falsos positivos de homologación con casos etiquetados.
- Reconciliación por identificador de evento cuando exista; estrategias específicas por fuente cuando no exista. Reportar coincidencias uno a uno, ambiguas y huérfanas.

### 6.3 Análisis multicapa y temporal

- Consultas que unan flujos y relaciones vigentes en una ventana: `empresa -> representante -> otra empresa` junto a transferencias, o `servidor -> grupo de seguridad -> servidor` junto a comunicaciones.
- Detectores temporales: ráfagas, periodicidad, cambios de línea base, caminos ordenados por tiempo y ciclos realizables dentro de una ventana. Separar un ciclo en el grafo agregado de un recorrido temporal plausible.
- Simulación de interrupción: retirar nodo o arista y recalcular conectividad y rutas accesibles, especialmente para logística y SOC. Presentar hipótesis y supuestos, no predicciones causales.
- Métricas con semántica declarada: PageRank ponderado por intensidad si aplica; intermediación por saltos o por distancia/coste justificado; aproximaciones sólo con etiqueta y error conocido. Evitar sumar aristas con unidades distintas.

### 6.4 Experiencia de investigación

- Vista de caso con filtros compartidos, línea de tiempo, subgrafo de evidencia y panel de calidad de datos. Desde cualquier hallazgo, llegar a los eventos y relaciones que lo produjeron.
- Comparar ventanas y guardar una selección de nodos/filtros como investigación reproducible. Exportar hallazgos con sus parámetros y referencias, además de la tabla filtrada.
- Distinguir visualmente observaciones confirmadas, fusiones propuestas, extremos desconocidos y aristas agregadas. Mostrar unidad, período y regla de agregación en cada gráfico.
- Permitir que el analista marque hallazgos como revisados, descartados o pendientes, con motivo. Usar ese retorno para mejorar reglas; no convertirlo directamente en un modelo opaco.

### 6.5 Rendimiento y extensibilidad

- Agregación tabular y persistencia columnar para datos grandes; construir únicamente el subgrafo que se explora. Benchmark reproducible en 10 mil, 100 mil y 1 millón de eventos sintéticos antes de elegir tecnologías adicionales.
- Catálogo de detectores con interfaz estable (`inputs`, `parameters`, `run`, `evidence`) y perfiles instalables. Un detector genérico nunca debe asumir que `quantity` significa dinero.
- Interfaz Python y CLI antes de abrir una API de servicio. Una API y persistencia centralizada entrarían cuando aparezcan necesidades reales de concurrencia o integración.

## 7. Arquitectura objetivo y límites de módulos

| Módulo propuesto | Responsabilidad | Evolución desde el código actual |
|---|---|---|
| `connectors` | Leer fuentes y conservar referencias originales. | Separar SQL corporativo de `sources.py`; convertir Excel y sintético en adaptadores independientes. |
| `schema` / `quality` | Validar contratos, unidades y fechas; producir rechazos y métricas. | Fortalecer `normalize.py` y `validation.py`. |
| `identity` | Canonizar entidades con decisiones rastreables. | Reemplazar la homologación automática indiscriminada de `homologate.py`. |
| `reconcile` | Resolver observaciones espejo y duplicados según el perfil. | Encapsular `dedup.py` como estrategia financiera. |
| `graph` / `analytics` | Proyectar grafos por tiempo y capa, calcular métricas y detectores. | Generalizar `graphs.py` y `analytics.py` sin perder el perfil financiero. |
| `profiles` | Reglas y etiquetas sectoriales versionadas. | Sacar constantes bancarias del núcleo, del dashboard y del YAML único. |
| `ui` / `cli` | Presentar y exportar investigaciones. | Mantener Streamlit como cliente; añadir CLI mínima. |

La separación no exige crear todos estos paquetes de inmediato. Primero conviene fijar los contratos públicos y mover cada regla cuando haya un segundo perfil que la necesite.

## 8. Ruta de implementación y entregables

Las duraciones son una estimación para priorizar, sujetas al tiempo disponible y al tamaño real de los datos.

| Etapa | Horizonte sugerido | Entregable verificable | Criterio de salida |
|---|---|---|---|
| **0. Preparación pública** | 2–4 semanas | Repositorio con datos y configuración ficticios, licencia elegida por el titular, `pyproject.toml`, demo instalable, guía de contribución, pruebas y CI. | Alguien externo puede clonar, instalar y ejecutar el perfil financiero sintético sin SQL ni ediciones manuales. No hay datos o rutas corporativas en archivos ni historial a publicar. |
| **1. Exactitud y contrato general** | 1–3 meses | Identificadores como texto, esquema de eventos/relaciones, calidad de datos, reconciliación auditable, métricas con significado explícito. | Pruebas de regresión financiera y casos adversarios de identidad, duplicados y pesos pasan; cada cifra agregada remite a eventos. |
| **2. Prueba multisectorial** | 3–6 meses | Dos perfiles adicionales con datos sintéticos: SOC y logística; dashboard con unidades y términos dinámicos; CLI. | Los tres perfiles recorren el mismo núcleo y sus detectores de dominio están aislados; hay ejemplos ejecutables y documentación de mapeo. |
| **3. Investigación avanzada** | 6–12 meses | Relaciones con vigencia, detectores temporales y multicapa, revisión de hallazgos, exportación de evidencia, comparación de ventanas y benchmarks. | Un usuario puede reproducir un hallazgo con manifiesto, versión del detector y registros originales; se han medido rendimiento y límites. |
| **4. Ampliación opcional** | Tras validar adopción | Perfiles fiscal y ONA, API o despliegue multiusuario si hay demanda. | Privacidad, permisos, aislamiento y derechos de datos definidos para cada entorno. |

### Primeros issues propuestos

| Orden | Issue | Tamaño orientativo | Dependencia |
|---|---|---|---|
| 1 | Sanitizar configuración y documentación; crear `config.example.yaml` sintético y configuración privada externa. | S | Ninguna |
| 2 | Corregir la guía de inicio y hacer que `run_demo.py` seleccione explícitamente datos sintéticos. | S | 1 |
| 3 | Añadir `pyproject.toml` con dependencias opcionales (`sql`, `dashboard`) y verificar instalación desde cero. | M | 1 |
| 4 | Crear fixtures y pruebas de dirección, identificadores con ceros/IP, reconciliación y sumas conservadas. | M | 2 |
| 5 | Definir contrato versionado `Entidad` / `EventoFlujo` / `RelacionEntidad` y un adaptador financiero. | L | 4 |
| 6 | Rediseñar deduplicación y homologación con evidencias y casos ambiguos explícitos. | L | 5 |
| 7 | Revisar centralidad y separar peso de flujo de distancia topológica. | S | 4 |
| 8 | Incorporar perfil SOC sintético y adaptar etiquetas/unidades del dashboard. | L | 5–7 |
| 9 | Incorporar perfil logístico y detector de saturación por capacidad. | L | 8 |

## 9. Preparación para GitHub y adopción

**Antes del primer `git push`:** reemplazar servidor, NIT de prueba, rutas y cualquier dato derivado de sistemas internos; revisar consultas SQL, nombres de tablas, ejemplos, capturas y artefactos de salida con quien tenga autoridad sobre ellos. Si hubo un commit local previo con esos datos, limpiar el historial antes de hacerlo público. Agregar `.gitignore` para configuraciones privadas, `.env`, `aliases.json`, datos, reportes y cachés; no confiar en `.gitignore` para retirar información ya publicada. Activar escaneo de secretos como control adicional, de acuerdo con la [documentación de GitHub](https://docs.github.com/en/code-security/concepts/secret-security/secret-scanning).

**Paquete:** declarar metadatos, versión, compatibilidad de Python y dependencias en `pyproject.toml`; construir y probar wheel y sdist. Mantener `pyodbc` opcional para que un usuario de CSV/sintético no necesite un controlador SQL. La [guía oficial de empaquetado de Python](https://packaging.python.org/en/latest/tutorials/packaging-projects/) describe este flujo.

**Documentación pública:** README de instalación en cinco minutos, tutorial de cada perfil, referencia de esquema y configuración, explicación de detectores y límites, changelog, política de seguridad y guía de contribución. Conservar `DOCUMENTACION.md` como referencia del perfil financiero o migrarla gradualmente a una sección de arquitectura; corregir los pasajes que hablan de un dashboard futuro cuando ya existe.

**Calidad:** CI en las versiones de Python declaradas, formato y análisis estático, pruebas unitarias con casos adversarios, pruebas de integración sintéticas y prueba de construcción del paquete. Añadir benchmarks separados de CI normal para que el rendimiento tenga una línea base comparable.

**Privacidad y uso responsable:** los perfiles SOC y ONA pueden procesar identificadores personales o sensibles. Un despliegue multiusuario requeriría aislamiento por caso, permisos de acceso, almacenamiento de anotaciones fuera del paquete, controles de exportación y retención definida. En la app actual, `st.cache_resource` y `aliases.json` son adecuados sólo para un contexto local controlado hasta que se verifique su aislamiento.

## 10. Decisiones de producto que conviene cerrar temprano

1. **Audiencia inicial:** analistas técnicos que ejecutan Python/Streamlit localmente. Esta elección permite publicar pronto y aprender de usuarios reales antes de diseñar un servicio hospedado.
2. **Nombre y alcance:** mantener `red_flujos` para el paquete inicial y describirlo como análisis de redes de eventos. Un cambio de nombre puede decidirse al tener ejemplos de tres sectores.
3. **Licencia:** elegir explícitamente una licencia abierta compatible con el código y datos que sí se pueden distribuir; verificar la titularidad antes de incorporarlos.
4. **Datos de ejemplo:** únicamente sintéticos o públicos con condiciones de reutilización verificadas. Ningún caso real debe ser requisito para reproducir los tutoriales.
5. **Umbrales y alertas:** cada perfil propone valores iniciales, pero el usuario ve su justificación y puede calibrarlos. Los hallazgos no emiten decisiones automáticas sobre personas o entidades.

## 11. Qué significaría una versión 1.0 sólida

- Instalación y demo reproducibles en un equipo sin acceso a infraestructura privada.
- Al menos tres perfiles con el mismo contrato central y datos de ejemplo seguros.
- Ninguna pérdida silenciosa de identificadores, unidades, fechas o registros descartados.
- Reconciliación y resolución de identidad explicables y revisables.
- Resultados enlazados con su procedencia, filtros, versión y evidencia.
- Interfaz y API Python documentadas, pruebas y CI continuas, límites de rendimiento medidos.
- Publicación con licencia, guía de contribución y mantenimiento definido.

La primera entrega valiosa no necesita abarcar toda la visión: **hacer público y confiable el perfil financiero actual** crea una base real sobre la cual validar si la arquitectura general sirve a los otros sectores.
