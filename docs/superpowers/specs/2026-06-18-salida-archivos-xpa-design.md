# Diseño — Cambios de salida: quitar "Grand total" y agregar "Archivos XPA"

**Fecha:** 2026-06-18
**Proyecto:** Cloud Instance Verifier (app Flask local)

## Contexto

La app lee un Excel con links de AWS Calculator, consulta la API de CloudFront,
agrega las instancias y genera **un único `.xlsx`** de salida. El tipo de salida
se elige con 3 radio-buttons en la UI:

- **By company** (`summarize_by="company"`) → columnas `#, Provider, Instance, Quantity, Company` (+ `Processor` en AWS)
- **Grand total** (`summarize_by="total"`) → columnas `#, Provider, Instance, Quantity` (+ `Processor`)
- **Detailed** (`summarize_by="none"`) → una fila por aparición

Archivos relevantes:
- [excel_processor.py](../../../excel_processor.py) — `process_excel_file()` calcula `raw_results` y construye el DataFrame de salida.
- [app.py](../../../app.py) — rutas Flask, worker en hilo, `/download` entrega el `.xlsx`.
- [templates/index.html](../../../templates/index.html) — UI; radios de "Output type"; `summarize_by` se envía en el form.

## Objetivo

1. **Eliminar** el botón/opción **"Grand total"** (`summarize_by="total"`).
2. **Agregar** un nuevo tipo de salida **"Archivos XPA"** (`summarize_by="xpa"`).

Tras el cambio, los tipos de salida son: **By company**, **Detailed**, **Archivos XPA**.

## Especificación del modo "Archivos XPA"

- Genera **un archivo `.xlsx` por empresa** presente en los datos.
- Todos los archivos se empaquetan en un **único `.zip`** que el usuario descarga.
- **Nombre de cada archivo:** `{Empresa}_{Año}_{mes}.xlsx`
  - Año y mes = fecha de hoy (cuando se procesa).
  - Mes en **español, en minúscula y nombre completo** (enero, febrero, …, junio, …).
  - Ejemplo: `Esfera_2026_junio.xlsx`.
- **Contenido de cada archivo (hoja única):**
  - **Sin fila de encabezados** (la primera fila ya son datos).
  - **4 columnas, en este orden:**
    1. `#` — número de fila, **reinicia en 1** en cada archivo.
    2. `Provider` — el proveedor cloud seleccionado (ej. `AWS`).
    3. `Instance` — tipo de instancia.
    4. `Quantity` — cantidad total para esa instancia en esa empresa.
  - **Agrupado:** las cantidades se **suman por tipo de instancia** dentro de cada empresa
    (misma lógica que "By company", pero separado por empresa y sin la columna `Company`
    ni la columna `Processor`).
  - Orden de filas dentro del archivo: por tipo de instancia (orden alfabético), consistente con el modo "By company".

### Reglas de borde

- **Nombre de archivo seguro:** del nombre de empresa se eliminan/sustituyen los caracteres
  inválidos para nombres de archivo en Windows: `/ \ : * ? " < > |`. Se recortan espacios
  sobrantes en los extremos.
- **Empresa vacía:** las filas cuyo nombre de empresa esté vacío se agrupan en un archivo
  llamado `SinEmpresa_{Año}_{mes}.xlsx`.
- **Requiere columna Customer:** el modo XPA necesita la columna *Customer* configurada en la UI;
  si está vacía, no es posible separar por empresa → se devuelve un **error claro** al usuario
  ("El modo Archivos XPA requiere configurar la columna Customer").
- **Sin resultados:** si no se encontró ninguna instancia, se entrega un `.zip` vacío
  (o, alternativamente, un error informativo — ver "Pendiente menor").
- **Nombres de empresa duplicados tras limpieza:** si dos empresas distintas quedan con el
  mismo nombre de archivo, sus filas se combinan en el mismo archivo (es el resultado natural
  de agrupar por nombre de empresa).

## Arquitectura del cambio

Enfoque: **cambio contenido, sin alterar la arquitectura existente**.

### Backend — `excel_processor.py`

- Se reutiliza el cálculo de `raw_results` (lista de `{customer, instance, count}`).
- Nueva rama para `summarize_by == "xpa"`: en lugar de devolver un solo `DataFrame`,
  agrupa por `(empresa, instancia)` sumando cantidades y devuelve los datos **organizados por empresa**.
- Forma de retorno propuesta: una función/retorno que entregue un
  `dict[str, pandas.DataFrame]` → `{ nombre_empresa: df_4_columnas }`,
  donde cada `df` tiene las columnas `#, Provider, Instance, Quantity` (con `#` reiniciado por empresa).
  - Para no romper la firma actual (que devuelve `DataFrame`), el modo `xpa` se maneja con
    una función dedicada (p. ej. `build_xpa_groups(raw_results, provider) -> dict[str, DataFrame]`),
    llamada desde el worker, o `process_excel_file` devuelve el dict cuando `summarize_by=="xpa"`.
    La decisión final de firma se cierra en el plan de implementación; el contrato es:
    **modo xpa ⇒ datos agrupados por empresa, 4 columnas, sin encabezado.**

### Backend — `app.py` (worker + descarga)

- El worker detecta el modo:
  - **xpa:** por cada empresa escribe un `.xlsx` con `to_excel(..., index=False, header=False)`;
    todos se agregan a un `zipfile.ZipFile` en memoria (`io.BytesIO`). El resultado del job
    son los bytes del `.zip`. Se guarda también el tipo de salida (`"zip"`/`"xlsx"`) en el job.
  - **resto (company/none):** comportamiento actual, un solo `.xlsx`.
- `/download`:
  - **xpa:** `mimetype="application/zip"`, `download_name="archivos_xpa_{Año}_{mes}.zip"`.
  - **resto:** igual que hoy (`...sheet`, `cloud_instances_verificadas.xlsx`).
  - El nombre/mimetype se derivan del tipo de salida guardado en el job.
- Validación: si `summarize_by=="xpa"` y `customer_column` viene vacío → responder error
  (en `/process` antes de lanzar el worker, o marcar el job en error con mensaje claro).

### Frontend — `templates/index.html`

- **Quitar** el radio "Grand total" (`id="sumTotal"`, `value="total"`).
- **Agregar** un radio "Archivos XPA" (`value="xpa"`), por ejemplo con icono de carpeta/zip.
- El resto del JS (`summarize_by` se toma del radio seleccionado) no cambia; la descarga sigue
  usando el mismo botón/endpoint, que ahora puede entregar un `.zip`.

## Flujo de datos (modo xpa)

```
Excel subido
  → process_excel_file (extrae links, consulta API, arma raw_results)
  → agrupar por (empresa, instancia) sumando count
  → dict { empresa: DataFrame[#, Provider, Instance, Quantity] }
  → worker: por empresa → .xlsx (sin header) → ZipFile en memoria
  → job.result = bytes(zip), job.kind = "zip"
  → /download → archivos_xpa_2026_junio.zip
```

## Pruebas

- **Unitario `excel_processor`:** dado un `raw_results` con 2 empresas y varias instancias,
  `build_xpa_groups` devuelve 2 grupos, cantidades sumadas por instancia, `#` reiniciado por empresa,
  columnas exactas `#, Provider, Instance, Quantity`.
- **Borde:** empresa vacía → grupo `SinEmpresa`; nombre con caracteres inválidos → saneado.
- **Integración `app`:** POST `/process` con `summarize_by=xpa` y customer configurado →
  job termina, `/download` devuelve un `.zip` con un `.xlsx` por empresa, cada uno **sin encabezado**
  y con 4 columnas.
- **Validación:** `summarize_by=xpa` sin `customer_column` → error claro, no se lanza el worker.
- **Regresión:** modos `company` y `none` siguen devolviendo un único `.xlsx` igual que antes;
  `total` ya no es seleccionable en la UI.

## Pendiente menor (confirmar en revisión)

- Comportamiento exacto cuando **no hay resultados** en modo xpa: ¿zip vacío o error informativo?
  (Propuesta: zip vacío + mensaje en el log.)
- Idioma/capitalización del mes confirmados: **español, minúscula, nombre completo**.
- ¿Se elimina del backend la rama `summarize_by=="total"` o solo se oculta en la UI?
  (Propuesta: ocultar en UI y **conservar** la rama backend, inofensiva, para no romper nada;
  o eliminarla si se prefiere limpieza total.)
