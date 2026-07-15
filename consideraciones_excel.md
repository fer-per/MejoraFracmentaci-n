# Consideraciones y Estructura del Inventario Excel

El **Sistema de Automatización Archivística** depende de un archivo Excel (`.xlsx`) estructurado de manera particular. A continuación se detallan las especificaciones técnicas, las filas de control, las columnas requeridas y las reglas de depuración de datos que aplica el sistema.

---

## 1. Estructura y Distribución de Filas
El archivo Excel no debe comenzar directamente con los datos de los registros. El sistema espera una cabecera con metadatos globales en las primeras filas, seguida por los encabezados de columnas.

Según se define en [configuracion.py](file:///c:/Users/GRA/Videos/fracFER/Fracmentaci-n-protocolos/configuracion.py):
*   **Fila 4 (Metadato Siglo)**: Debe contener la información del siglo en la primera celda (Columna A). El sistema busca un patrón de texto como `Seccion: XVI` para extraer el valor (ej. `XVI`).
*   **Fila 7 (Metadato Acervo)**: Debe contener el código del fondo documental en la primera celda (Columna A). Busca un patrón de tipo `Código del fondo: N7` para extraer el número de acervo (ej. `7`).
*   **Fila 8 (Encabezados de Columnas)**: Es la fila donde se ubican los nombres de las columnas que lee el script (ej: `N° DE REGISTRO`, `N° DE FOLIOS`, etc.).
*   **Fila 9 (Sub-encabezados)**: Opcional o complementaria (en algunos inventarios se usa para especificar `FECHA INICIAL` y `FECHA FINAL` bajo la categoría de *DATA CRÓNICA*).
*   **Filas 10+ (Registros)**: Filas de datos que corresponden a los documentos a procesar.

> [!NOTE]
> Al procesar el inventario, el cargador de datos omite las primeras 7 filas (`FILAS_A_OMITIR = 7`) de manera que la fila 8 se interpreta como el encabezado de las columnas en el DataFrame de pandas.

---

## 2. Metadatos Globales Extraídos del Excel
Los metadatos se cargan al inicio del proceso para definir la estructura de carpetas de destino:
1.  **Siglo (Fila 4, Columna A)**:
    *   *Lectura*: Busca texto después del caracter `:` (dos puntos).
    *   *Conversión*: Si el siglo extraído está en números romanos (ej: `XVI`), el sistema lo convierte automáticamente a numeración arábiga (`16`) para el nombre de la carpeta física (`SIGLO 16`).
2.  **Acervo (Fila 7, Columna A)**:
    *   *Lectura*: Busca el patrón `N` seguido de dígitos (ej: `N7` o `n07`). Extrae el número (`7`).

---

## 3. Mapeo de Columnas (Fila 8)
El script busca columnas específicas basándose en nombres unificados en la configuración. Es crítico respetar las mayúsculas/minúsculas y la existencia de caracteres especiales (como saltos de línea):

| Nombre Físico en Excel | Variable Interna | Uso en el Sistema |
| :--- | :--- | :--- |
| `N° DE REGISTRO` | `registro_id` | Identificador único del registro para nombrar la carpeta (`REGISTRO {registro_id}`). |
| `ESCRIBANO/\nNOTARIO` | `escribano` | Nombre del notario o escribano. **Atención**: La celda del encabezado contiene un salto de línea (`\n`). |
| `N° DE PROT.` | `protocolo` | Número del protocolo notarial. Se usa para la carpeta (`PROTOCOLO {protocolo}`). |
| `N° DE FOLIOS` | `folios_origen` | Rango de folios físico (ej. `1r-2v`, `5v-7r`). **Campo crítico** para calcular las páginas del PDF. |
| `DATA TÓPICA (Lugar)` | `lugar` | Ubicación geográfica. Validada por el analizador de Data Tópica. |
| `FECHA INICIAL` | `fecha_inicio` | Fecha de inicio del documento (formato esperado `d/m/yyyy`). Determina el año (carpeta de nivel 5) y el mes (carpeta de nivel 9). |
| `FECHA FINAL` | `fecha_fin` | Fecha de finalización del documento. Validada contra la inicial. |
| `Titulo estandar` | `titulo` | Título normalizado del documento. Se usa para la carpeta de nivel 8 (`{titulo}`). |
| `INTERESADO 1` | `interesado1` | Nombre del primer interesado. Su primer nombre/apellido define la carpeta de nivel 10. |
| `INTERESADO 2` | `interesado2` | Nombre del segundo interesado. Su primer nombre/apellido define el nombre del archivo PDF final. |
| `OBSERVACIONES` | `observaciones` | Notas adicionales del registro (opcional). |

> [!TIP]
> Si el Excel contiene columnas de fechas que se llaman `DATA CRÓNICA 1` y `DATA CRÓNICA 2` (o variantes que contengan `"DATA CR"`), el sistema las mapea y renombra automáticamente a `FECHA INICIAL` y `FECHA FINAL` para asegurar la compatibilidad.

---

## 4. Reglas de Depuración y Omisión de Datos
Al leer el archivo mediante [RepositorioExcelPandas.cargar_registros](file:///c:/Users/GRA/Videos/fracFER/Fracmentaci-n-protocolos/modules/infraestructura/adaptadores.py#L111-L178), se aplican las siguientes reglas de limpieza automática:
1.  **Limpieza de Espacios**: Todos los nombres de las columnas y los valores de las celdas se someten a `.strip()` para remover espacios en blanco accidentales al inicio y final del texto.
2.  **Ignorar Columnas Vacías**: Se eliminan columnas sin nombre asignado (columnas que inician con `Unnamed:` en pandas).
3.  **Filtro de Marcadores de Sección (Filas Decorativas)**: 
    *   Los archivistas a veces insertan filas completas para dividir secciones (ej. `"Protocolo N° 4"` o `"Registro de 1785"`).
    *   El cargador de datos verifica la primera columna de cada fila. Si coincide con la expresión regular `^\s*(protocolo|registro)\b` (ignorando mayúsculas/minúsculas), la fila entera se **omite**, evitando fallos por filas que no contienen metadatos de documentos.
4.  **Cálculo de la Fila Real de Excel**:
    *   Para reportar errores al usuario en el panel y en el archivo de pendientes (`pendientes.csv`), el sistema calcula la fila exacta del Excel usando la fórmula: `fila_excel = index_pandas + FILAS_A_OMITIR + 2`.
    *   Esto permite al usuario ubicar de inmediato la fila en su visor de Excel (ej: Fila `35`).
5.  **Valores Vacíos**: Las celdas vacías o con valor `NaN` son convertidas a cadenas de texto vacías (`""`) para evitar errores de tipo `NoneType`.
