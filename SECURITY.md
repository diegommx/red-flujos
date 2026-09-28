# Seguridad y datos

No publique datos de análisis, archivos de configuración privados, credenciales,
identificadores internos ni capturas de casos reales en issues o pull requests.

El paquete público no contiene consultas ni servidores de una organización.
Use un archivo `*.local.yaml` fuera del control de versiones para la conexión
SQL y las reglas de mapeo de su caso. Para autenticación SQL, establezca
`RF_SQL_USER` y `RF_SQL_PASSWORD` como variables de entorno locales.
Use permisos SQL de sólo lectura y filtros de caso en las consultas. El límite
`fuente.sql.max_rows` evita cargar accidentalmente más filas de las previstas.

El dashboard carga datos en la memoria de la sesión y permite exportar los
eventos filtrados. Ejecútelo en un entorno cuyo acceso corresponda a la
sensibilidad de sus datos. La versión actual no implementa autenticación ni
permisos para un servicio multiusuario. La configuración incluida limita la
escucha de Streamlit a `127.0.0.1`; no cambie esa dirección para datos sensibles
sin incorporar antes autenticación y aislamiento.

Antes de informar una vulnerabilidad, retire de la reproducción cualquier
dato privado. Abra un issue sólo si puede describirla sin revelar secretos.

El iniciador de Windows guarda su registro técnico fuera del repositorio, en
`%LOCALAPPDATA%\red_flujos\iniciador.log`. No coloque datos privados en la
carpeta `examples/`. Antes de publicar, revise los archivos preparados para
Git, además de las reglas de `.gitignore`: estas reglas no eliminan datos que
se hayan incluido en commits anteriores.
