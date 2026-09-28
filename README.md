# red-flujos

Herramienta local en Python para explorar redes de flujos dirigidos y relaciones entre entidades. Incluye un ejemplo financiero **completamente sintético** y acepta CSV, Excel o consultas SQL Server definidas por cada usuario. Al abrir el dashboard se elige la fuente; el programa no intenta conectarse a ningún servidor por defecto.

> Estado: primera evolución pública del motor financiero. El contrato general de eventos y los perfiles sectoriales avanzados están descritos en [PROPUESTA_EVOLUCION.md](PROPUESTA_EVOLUCION.md); todavía no son funciones disponibles.

## Primer uso

En Windows, instale **Python 3.10 o superior** y haga doble clic en [`INICIAR_RED_FLUJOS.cmd`](INICIAR_RED_FLUJOS.cmd). Se abre una ventana con el botón **Iniciar proyecto**. La primera vez crea el entorno e instala las dependencias; después abre la aplicación en el navegador. En la primera pantalla, pulse **Explorar datos ficticios** para cargar los [CSV de demostración](examples/demo_financiero/README.md) sin aportar archivos propios. También puede elegir CSV, Excel o SQL Server. El iniciador ofrece **Detener** para cerrar el servidor local.

Si descarga el repositorio como ZIP desde GitHub, extráigalo antes de hacer doble clic. El iniciador solo abre la aplicación en `127.0.0.1` y guarda su registro técnico fuera del repositorio, en la carpeta local de aplicaciones del usuario. Para funcionar por primera vez necesita acceso a Internet para instalar las dependencias de Python.

Como alternativa, en terminal:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dashboard]"
.venv\Scripts\streamlit run app.py
```

En Linux/macOS, active el entorno con `source .venv/bin/activate` y ejecute `pip install -e ".[dashboard]"` y `streamlit run app.py`. La primera pantalla permite explorar los CSV ficticios incluidos o elegir **Ejemplo sintético, CSV, Excel o SQL Server**. Sólo se carga la fuente al pulsar el botón correspondiente.

Por consola:

```powershell
.venv\Scripts\red-flujos                # pregunta la fuente
.venv\Scripts\red-flujos --source synthetic
```

El núcleo sin interfaz se instala con `pip install -e .`. Para Excel use `.[excel]`; para SQL Server, `.[sql]` y un controlador ODBC instalado en su equipo. `requirements.txt` instala todas las opciones tradicionales.

## Sus propios CSV o Excel

En el dashboard cargue el archivo de flujos y, si existen, los archivos de relaciones y nombres. Los archivos se leen en memoria. Para probar un formato distinto del financiero, use los archivos ficticios de [`examples/`](examples/) y seleccione [`logistica.example.yaml`](examples/logistica.example.yaml) como YAML de mapeo; también puede usar la CLI:

```powershell
.venv\Scripts\red-flujos --source csv --transactions examples/flujos.csv --relations examples/relaciones.csv --config examples/logistica.example.yaml
```

Columnas del archivo de flujos de ejemplo:

| Columna | Significado |
|---|---|
| `id_evento` | Identificador único del registro; recomendado para detectar copias exactas. |
| `actor` | Entidad observada. Se conserva como texto, incluidos ceros iniciales e IP. |
| `contraparte` | Otro extremo. Puede estar vacío; cada vacío es un extremo desconocido independiente. |
| `fecha` | Fecha y, preferiblemente, hora del evento. |
| `cantidad` | Número positivo; su unidad se declara en `presentacion.unidad`. |
| `tipo_evento` | Determina la dirección con `transaccion.mapa_sentido`: `DEBITO` significa actor → contraparte y `CREDITO` el sentido inverso. |
| `canal`, `modalidad`, `tipo_actor`, `nombre_contraparte` | Atributos opcionales para vistas y nombres. |

Las relaciones opcionales usan `entidad`, `relacionado`, `tipo_relacion` y opcionalmente `nombre_entidad`, `nombre_relacionado`, `estado`, `categoria`. Una tabla de nombres opcional usa `id`, `nombre`. Los nombres de columnas pueden reemplazarse mediante `columnas_transaccional`, `columnas_vinculados` y `columnas_nombres` en un YAML privado; este YAML se fusiona con los valores públicos de `red_flujos/config.yaml`.

Si la fuente registra cada operación tanto desde el emisor como desde el receptor, active la casilla de **registros espejo**. El motor sólo reconcilia pares internos inequívocos con igual dirección real, instante, cantidad y canal. Los grupos ambiguos se conservan y se reportan.

## SQL Server sin compartir la configuración de su organización

El paquete no contiene servidor, consultas SQL ni credenciales. Copie [`examples/sql.example.yaml`](examples/sql.example.yaml) como `mi_caso.local.yaml` y edítelo localmente. Los archivos `*.local.yaml` están excluidos por `.gitignore`. Especifique consultas que devuelvan las columnas del mapeo; convierta los IDs a texto en la consulta y limite el universo con parámetros `?`. `max_rows` detiene lecturas que superen el límite configurado; también use una cuenta de base de datos de sólo lectura.

En la primera pantalla, elija **SQL Server** y señale la ruta del YAML privado. La autenticación integrada de Windows se usa si `trusted_connection: true`. Para autenticación SQL, establezca `RF_SQL_USER` y `RF_SQL_PASSWORD` en el entorno y use `trusted_connection: false`; nunca escriba una contraseña en el YAML. La CLI equivalente es:

```powershell
.venv\Scripts\red-flujos --source sql --config mi_caso.local.yaml
```

La lectura SQL requiere `pyodbc` y un controlador ODBC instalado por separado. Las consultas y permisos pertenecen al usuario que ejecuta la herramienta.

## Qué calcula

1. Valida columnas, dirección, fechas, cantidades e identificadores; informa descartes.
2. Homologa identificadores exactos por defecto. La unión por prefijo y nombre es opcional y produce un reporte de decisiones y conflictos.
3. Reconcilia observaciones espejo sólo si se configura. Conserva eventos ambiguos.
4. Construye el grafo dirigido de flujos y el grafo de relaciones; excluye extremos desconocidos de centralidad y ciclos, aunque los muestra agregados en la vista.
5. Calcula totales, canales, flujos entre actores, PageRank, intermediación por número de saltos, ciclos cortos y entidades relacionadas compartidas.

La versión actual usa un modelo interno heredado del perfil financiero (`nit`, `valor`, `transaccion`) aunque el mapeo de entrada, los identificadores, la unidad y las etiquetas de presentación son configurables. Un hallazgo topológico es una pista de investigación, no una prueba de conducta indebida.

## Privacidad y publicación

- El dashboard guarda resultados y alias en la **sesión**, sin escribir los archivos cargados dentro del paquete. El botón «Cambiar fuente de datos» descarta el resultado de la sesión.
- La carpeta `examples/demo_financiero/` contiene únicamente datos generados con identificadores y nombres ficticios. Los archivos personales y configuraciones locales están excluidos de Git mediante `.gitignore`; revise también el contenido antes de cada publicación.
- La app ofrece descarga de los eventos filtrados. Ejecútela sólo en un entorno con acceso acorde a sus datos; esta versión no incorpora autenticación multiusuario.
- No incluya YAML privados, datos, capturas o reportes reales en commits e issues. Revise todo el contenido y los derechos sobre el código y los datos antes de publicar el repositorio. Consulte [SECURITY.md](SECURITY.md).
- Antes de compartir, ejecute `python scripts/auditar_publicacion.py`: revisa archivos incluidos en Git en busca de secretos comunes, correos y rutas de usuario. Este control automático no reemplaza la revisión humana de los archivos.

## Desarrollo

```powershell
.venv\Scripts\python -m pip install -e ".[dashboard,test]"
.venv\Scripts\python -m pytest -q
.venv\Scripts\red-flujos --source synthetic
```

Arquitectura y límites actuales: [DOCUMENTACION.md](DOCUMENTACION.md). Contribuciones: [CONTRIBUTING.md](CONTRIBUTING.md). Licencia del código de este repositorio: [MIT](LICENSE); confirmar su titularidad antes de publicarlo junto con material previo de una organización.
