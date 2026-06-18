# Calc_Cloud — Verificador multinube de instancias

Las preferencias globales de trabajo, estilo y seguridad están en `~/.claude/CLAUDE.md`.
Este archivo cubre solo lo propio del proyecto.

## Qué es

Aplicación Flask local que procesa un archivo Excel con enlaces de calculadoras de
precios de nube. Por cada enlace obtiene la estimación, extrae los tipos de instancia
con sus cantidades, clasifica el procesador (Intel / AMD / Graviton) y exporta un Excel
resumido.

Está diseñada como multinube (tres proveedores), pero hoy solo **AWS está
implementado y funcional**. La UI ofrece un selector `cloud_provider`, pero Azure y GCP
aún no tienen lógica de obtención ni de parseo.

## Cómo correr

- Primera vez: `install.bat` (instala dependencias).
- Uso normal: `run.bat` (inicia el servidor y abre http://localhost:5000).
- Desarrollo: `python app.py`.

## Estructura del proyecto

```
Calc_Cloud/
├── app.py                 # Rutas Flask y store de trabajos en memoria
├── excel_processor.py     # Lectura del Excel y armado del resumen
├── aws_calculator.py      # Obtención y parseo de estimaciones de AWS
├── templates/
│   └── index.html         # Interfaz web de una sola página
├── ejemplos/              # Archivos de entrada para verificación manual
├── requirements.txt       # Dependencias de Python
├── install.bat            # Instalación de dependencias (primera vez)
├── run.bat                # Inicia el servidor y abre el navegador
├── INSTALL.txt            # Guía de instalación para el usuario final
├── README.md              # Documentación principal del proyecto
└── CLAUDE.md              # Este archivo
```

## Mantenimiento de la documentación

- Si cambias la estructura del proyecto (agregar, quitar, mover o renombrar archivos o
  módulos), actualiza la sección "Estructura del proyecto" de este archivo.
- El mismo cambio debe reflejarse en `README.md`. CLAUDE.md y README deben describir
  siempre la estructura y el funcionamiento reales.

## Arquitectura y flujo de datos

Tres módulos:

- `app.py` — rutas Flask y store de trabajos en memoria. El procesamiento corre en un
  hilo por trabajo; el cliente consulta el progreso con polling a `/status/<job_id>`.
- `excel_processor.py` — lee el Excel, localiza filas con enlaces, orquesta la
  obtención y arma el resumen (`none`, `company` o `total`).
- `aws_calculator.py` — obtiene la estimación, recorre el árbol JSON para acumular
  conteos de instancias y clasifica el procesador.

Flujo: Excel -> URLs de calculadora -> JSON de estimación -> conteo por tipo de
instancia -> resumen -> Excel de salida.

## Idiomas de los archivos

Los archivos del proyecto pueden estar en español, inglés o portugués. La UI y los
mensajes al usuario están mayormente en portugués; el código y los nombres en inglés.
No es necesario uniformar el idioma.

## Invariantes (no romper)

Cambios aquí provocan regresiones silenciosas en los resultados:

- El usuario indica las columnas por letra (enlaces, cliente) y la fila de encabezado.
  La conversión letra -> índice y el encabezado base 1 deben respetarse.
- El orden y los nombres de las columnas de salida (`#`, `Provider`, `Instance`,
  `Quantity`, `Company`, `Processor`) son el contrato con quien consume el Excel.
- La columna `Processor` solo se agrega cuando el proveedor es AWS.
- Las reglas de `classify_processor` siguen la convención de nombres de AWS. No las
  cambies sin verificar contra tipos de instancia reales.

## Cómo extender a otro proveedor (Azure / GCP)

Las tres piezas atadas a AWS que habría que generalizar:

1. La obtención de la estimación en `aws_calculator.py`, hoy fija al CDN de AWS.
2. El recorrido del árbol JSON, específico del formato de estimación de AWS.
3. `classify_processor`, basado en la nomenclatura de instancias de AWS.

`excel_processor.py` importa directamente las funciones de AWS; para multinube real
habría que seleccionar el módulo de proveedor según `cloud_provider`.

## Seguridad específica de esta app

- La app obtiene URLs provistas por el usuario: limita los destinos permitidos para
  evitar SSRF (acepta solo dominios de calculadoras conocidas).
- Hay un límite de tamaño de subida configurado; revísalo si cambian los archivos de
  entrada.
- No persistas ni registres el contenido de los archivos subidos.

## Notas operativas

- El store de trabajos es en memoria y single-user por diseño: reiniciar el servidor
  pierde los trabajos en curso y sus resultados.
- La carpeta `ejemplos/` contiene archivos de entrada para verificación manual.

## Problemas conocidos

- Dependencia heredada de Playwright / Chromium en `install.bat`, `requirements.txt` y
  la ruta `/check-deps`. Ya no se usa: la obtención real va por `requests` contra la API
  pública. Es candidata a limpieza.
