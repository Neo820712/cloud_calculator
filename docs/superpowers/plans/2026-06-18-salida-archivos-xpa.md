# Salida "Archivos XPA" + quitar "Grand total" — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminar el modo de salida "Grand total" de la UI y agregar un modo "Archivos XPA" que genera un `.xlsx` por empresa (4 columnas, sin encabezado) empaquetados en un `.zip`.

**Architecture:** Cambio contenido sin alterar la arquitectura. `excel_processor.py` gana helpers puros (nombre de mes en español, saneo de nombre de archivo) y una función `build_xpa_groups` que agrupa `raw_results` por empresa; `process_excel_file` devuelve un `dict[str, DataFrame]` cuando el modo es `xpa`. `app.py` detecta el modo en el worker: empaqueta cada empresa en un `.zip` en memoria y `/download` lo entrega como zip. La plantilla HTML cambia los radio-buttons.

**Tech Stack:** Python 3.14, Flask 3, pandas 3.0, openpyxl 3.1, pytest 9. `zipfile` y `datetime` de stdlib.

## Global Constraints

- Las pruebas se ejecutan desde la raíz del proyecto con `python -m pytest`.
- Mes en nombre de archivo: **español, minúscula, nombre completo** (enero…diciembre).
- Nombre de archivo por empresa: `{Empresa}_{Año}_{mes}.xlsx` (ej. `Esfera_2026_junio.xlsx`).
- Nombre del zip: `archivos_xpa_{Año}_{mes}.zip`.
- Cada `.xlsx` de empresa: **sin fila de encabezado**, 4 columnas en orden `#, Provider, Instance, Quantity`, con `#` reiniciando en 1 por archivo, agrupando (sumando) por tipo de instancia, instancias en orden alfabético.
- Caracteres inválidos en nombre de empresa (`\ / : * ? " < > |`) se sustituyen por `_`; empresa vacía → base `SinEmpresa`.
- Modo `xpa` requiere columna Customer configurada; si falta, error claro y no se lanza el worker.
- Sin resultados en `xpa` → zip vacío (no error).
- La rama backend `summarize_by=="total"` se **conserva** (inofensiva); solo se quita el radio de la UI.
- Mantener el estilo del código existente (sin type-checkers estrictos; docstrings breves).

---

## File Structure

- **Modify** `excel_processor.py` — agrega helpers `month_name_es`, `safe_company_filename`, `xpa_filename`, función `build_xpa_groups`, y rama `xpa` en `process_excel_file`.
- **Modify** `app.py` — validación de `xpa`, construcción del zip en el worker, `kind` en el job, `/download` con mimetype/nombre según `kind`.
- **Modify** `templates/index.html` — quitar radio "Grand total", agregar radio "Archivos XPA".
- **Create** `tests/test_xpa_helpers.py` — pruebas de helpers puros.
- **Create** `tests/test_xpa_groups.py` — pruebas de `build_xpa_groups`.
- **Create** `tests/test_process_xpa.py` — prueba de `process_excel_file` en modo `xpa` (con `fetch` monkeypatcheado).
- **Create** `tests/test_app_xpa.py` — pruebas de `/process`, `/download` y validación con el test client de Flask.
- **Create** `tests/test_template_radios.py` — verifica el HTML (radios) vía `GET /`.

---

### Task 1: Helpers puros (mes en español + nombre de archivo seguro)

**Files:**
- Modify: `excel_processor.py`
- Test: `tests/test_xpa_helpers.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `month_name_es(d: datetime.date) -> str` — nombre del mes en español, minúscula.
  - `safe_company_filename(company: str) -> str` — base de nombre de archivo segura; vacío/whitespace → `"SinEmpresa"`.
  - `xpa_filename(company: str, d: datetime.date) -> str` — `"{base}_{año}_{mes}.xlsx"`.

- [ ] **Step 1: Write the failing test**

Crear `tests/test_xpa_helpers.py`:

```python
from datetime import date

from excel_processor import month_name_es, safe_company_filename, xpa_filename


def test_month_name_es_returns_lowercase_spanish():
    assert month_name_es(date(2026, 6, 18)) == "junio"
    assert month_name_es(date(2026, 1, 1)) == "enero"
    assert month_name_es(date(2026, 12, 31)) == "diciembre"


def test_safe_company_filename_replaces_invalid_chars():
    assert safe_company_filename('A/B:C*?"<>|D\\E') == "A_B_C_____D_E"


def test_safe_company_filename_blank_becomes_sinempresa():
    assert safe_company_filename("") == "SinEmpresa"
    assert safe_company_filename("   ") == "SinEmpresa"


def test_xpa_filename_format():
    assert xpa_filename("Esfera", date(2026, 6, 18)) == "Esfera_2026_junio.xlsx"
    assert xpa_filename("", date(2026, 6, 18)) == "SinEmpresa_2026_junio.xlsx"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_xpa_helpers.py -v`
Expected: FAIL con `ImportError: cannot import name 'month_name_es'`.

- [ ] **Step 3: Write minimal implementation**

En `excel_processor.py`, añadir cerca de los imports (arriba del archivo, tras los imports existentes):

```python
import re
from datetime import date

_SPANISH_MONTHS = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}

_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')


def month_name_es(d: date) -> str:
    """Return the Spanish month name in lowercase for the given date."""
    return _SPANISH_MONTHS[d.month]


def safe_company_filename(company: str) -> str:
    """Sanitize a company name for use as a filename base.

    Replaces filesystem-invalid characters with '_'. Blank names become 'SinEmpresa'.
    """
    name = (company or "").strip()
    if not name:
        return "SinEmpresa"
    name = _INVALID_FILENAME_CHARS.sub("_", name).strip()
    return name or "SinEmpresa"


def xpa_filename(company: str, d: date) -> str:
    """Build the per-company XPA filename: '{base}_{year}_{month}.xlsx'."""
    return f"{safe_company_filename(company)}_{d.year}_{month_name_es(d)}.xlsx"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_xpa_helpers.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add excel_processor.py tests/test_xpa_helpers.py
git commit -m "feat: helpers de nombre de archivo XPA (mes ES + saneo)"
```

---

### Task 2: `build_xpa_groups` — agrupar resultados por empresa

**Files:**
- Modify: `excel_processor.py`
- Test: `tests/test_xpa_groups.py`

**Interfaces:**
- Consumes: `safe_company_filename` (Task 1).
- Produces:
  - `build_xpa_groups(raw_results: list[dict], provider: str) -> dict[str, pandas.DataFrame]`
    - `raw_results`: lista de `{"customer": str, "instance": str, "count": int}`.
    - Devuelve `dict` cuya clave es la **base de nombre saneada** de la empresa y el valor un
      `DataFrame` con columnas exactas `["#", "Provider", "Instance", "Quantity"]`, una fila por
      tipo de instancia (cantidades sumadas), instancias en orden alfabético, `#` desde 1 por grupo.
    - `raw_results` vacío → `{}`.

- [ ] **Step 1: Write the failing test**

Crear `tests/test_xpa_groups.py`:

```python
from excel_processor import build_xpa_groups


def test_groups_by_company_and_aggregates():
    raw = [
        {"customer": "Esfera", "instance": "m7i.large", "count": 2},
        {"customer": "Esfera", "instance": "m7i.large", "count": 3},
        {"customer": "Esfera", "instance": "c7g.xlarge", "count": 1},
        {"customer": "UOL", "instance": "t3.medium", "count": 4},
    ]
    groups = build_xpa_groups(raw, "AWS")

    assert set(groups.keys()) == {"Esfera", "UOL"}

    esfera = groups["Esfera"]
    assert list(esfera.columns) == ["#", "Provider", "Instance", "Quantity"]
    # instancias en orden alfabético, # desde 1, cantidades sumadas
    assert esfera["#"].tolist() == [1, 2]
    assert esfera["Instance"].tolist() == ["c7g.xlarge", "m7i.large"]
    assert esfera["Quantity"].tolist() == [1, 5]
    assert esfera["Provider"].tolist() == ["AWS", "AWS"]

    uol = groups["UOL"]
    assert uol["#"].tolist() == [1]
    assert uol["Quantity"].tolist() == [4]


def test_blank_company_goes_to_sinempresa():
    raw = [{"customer": "", "instance": "t3.large", "count": 1}]
    groups = build_xpa_groups(raw, "AWS")
    assert list(groups.keys()) == ["SinEmpresa"]


def test_empty_input_returns_empty_dict():
    assert build_xpa_groups([], "AWS") == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_xpa_groups.py -v`
Expected: FAIL con `ImportError: cannot import name 'build_xpa_groups'`.

- [ ] **Step 3: Write minimal implementation**

En `excel_processor.py` (después de `xpa_filename`, y `from collections import defaultdict` ya está importado arriba):

```python
def build_xpa_groups(raw_results: list[dict], provider: str) -> dict:
    """Group raw results into one DataFrame per company for XPA output.

    Returns {sanitized_company_base: DataFrame[#, Provider, Instance, Quantity]},
    quantities summed per instance, instances sorted alphabetically, # restarting at 1.
    """
    agg: dict[tuple, int] = defaultdict(int)
    for r in raw_results:
        key = safe_company_filename(r["customer"])
        agg[(key, r["instance"])] += r["count"]

    by_company: dict[str, list] = defaultdict(list)
    for (key, inst), cnt in sorted(agg.items()):
        by_company[key].append((inst, cnt))

    groups: dict = {}
    for key, items in by_company.items():
        rows = []
        for counter, (inst, cnt) in enumerate(items, start=1):
            rows.append({
                "#":        counter,
                "Provider": provider,
                "Instance": inst,
                "Quantity": cnt,
            })
        groups[key] = pd.DataFrame(rows, columns=["#", "Provider", "Instance", "Quantity"])
    return groups
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_xpa_groups.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add excel_processor.py tests/test_xpa_groups.py
git commit -m "feat: build_xpa_groups agrupa resultados por empresa"
```

---

### Task 3: Rama `xpa` en `process_excel_file`

**Files:**
- Modify: `excel_processor.py` (función `process_excel_file`, doc del parámetro `summarize_by` y la sección "Summarize & build output", aprox. líneas 20-108)
- Test: `tests/test_process_xpa.py`

**Interfaces:**
- Consumes: `build_xpa_groups` (Task 2), `fetch_estimate_instances` (existente).
- Produces: `process_excel_file(..., summarize_by="xpa", ...)` devuelve `dict[str, DataFrame]`
  (el mismo formato de `build_xpa_groups`). Para los demás modos sigue devolviendo `DataFrame`.

- [ ] **Step 1: Write the failing test**

Crear `tests/test_process_xpa.py`. Construye un Excel en memoria con 2 filas (empresa + link) y
monkeypatchea `fetch_estimate_instances` para no salir a la red:

```python
import io

import pandas as pd

import excel_processor


def _make_excel_bytes():
    # header en fila 1 (header_row=1). Col A = Customer (E? usamos posiciones simples).
    # Construimos columnas hasta 'J' para el link. Customer en col A, link en col B.
    df = pd.DataFrame({
        "Customer": ["Esfera", "UOL"],
        "Link": [
            "https://calculator.aws/#/estimate?id=AAA",
            "https://calculator.aws/#/estimate?id=BBB",
        ],
    })
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False)
    buf.seek(0)
    return buf.getvalue()


def test_process_excel_file_xpa_returns_dict_of_groups(monkeypatch):
    fake = {
        "AAA": {"m7i.large": 2},
        "BBB": {"t3.medium": 5},
    }

    def fake_fetch(url):
        if "AAA" in url:
            return fake["AAA"]
        return fake["BBB"]

    monkeypatch.setattr(excel_processor, "fetch_estimate_instances", fake_fetch)

    result = excel_processor.process_excel_file(
        _make_excel_bytes(),
        link_column="B",
        header_row=1,
        cloud_provider="AWS",
        customer_column="A",
        summarize_by="xpa",
    )

    assert isinstance(result, dict)
    assert set(result.keys()) == {"Esfera", "UOL"}
    esfera = result["Esfera"]
    assert list(esfera.columns) == ["#", "Provider", "Instance", "Quantity"]
    assert esfera["Instance"].tolist() == ["m7i.large"]
    assert esfera["Quantity"].tolist() == [2]


def test_process_excel_file_xpa_empty_returns_empty_dict(monkeypatch):
    monkeypatch.setattr(excel_processor, "fetch_estimate_instances", lambda url: {})
    result = excel_processor.process_excel_file(
        _make_excel_bytes(),
        link_column="B",
        header_row=1,
        cloud_provider="AWS",
        customer_column="A",
        summarize_by="xpa",
    )
    assert result == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_process_xpa.py -v`
Expected: FAIL — `process_excel_file` con `summarize_by="xpa"` cae en la rama `else` y devuelve un `DataFrame`, no un `dict` (assert `isinstance(result, dict)` falla).

- [ ] **Step 3: Write minimal implementation**

En `excel_processor.py`, dentro de `process_excel_file`, **antes** del bloque `if not raw_results:`
(actual línea ~102), insertar la rama xpa:

```python
    # ── XPA: un grupo (DataFrame) por empresa ─────────────────────────────────
    if summarize_by == "xpa":
        return build_xpa_groups(raw_results, cloud_provider)
```

Y actualizar el docstring del parámetro `summarize_by` para incluir:
`'xpa' → dict {empresa: DataFrame[#,Provider,Instance,Quantity]} (un archivo por empresa)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_process_xpa.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Run full suite (regresión)**

Run: `python -m pytest -v`
Expected: PASS (todos los tests previos siguen verdes).

- [ ] **Step 6: Commit**

```bash
git add excel_processor.py tests/test_process_xpa.py
git commit -m "feat: process_excel_file soporta modo xpa (dict por empresa)"
```

---

### Task 4: `app.py` — validación, zip en el worker y `/download`

**Files:**
- Modify: `app.py` (`process()` ~líneas 55-119, `worker()` ~86-112, `download()` ~136-146, init del job ~76-84)
- Test: `tests/test_app_xpa.py`

**Interfaces:**
- Consumes: `process_excel_file` (modo xpa → dict, Task 3), `xpa_filename`, `month_name_es` (Task 1).
- Produces:
  - `/process` rechaza con 400 si `summarize_by=="xpa"` y `customer_column` vacío
    (mensaje: `"O modo Archivos XPA requer a coluna Customer configurada."`).
  - Cada job guarda `kind` ∈ `{"xlsx", "zip"}`.
  - `/download` entrega zip (`application/zip`, `archivos_xpa_{año}_{mes}.zip`) cuando `kind=="zip"`,
    o el xlsx actual cuando `kind=="xlsx"`.

- [ ] **Step 1: Write the failing test**

Crear `tests/test_app_xpa.py`. Usa el test client de Flask y monkeypatchea `app.process_excel_file`
para no salir a la red ni leer Excel real:

```python
import io
import time
import zipfile

import pandas as pd

import app as flask_app


def _client():
    flask_app.app.config["TESTING"] = True
    return flask_app.app.test_client()


def _wait_done(client, job_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/status/{job_id}")
        data = r.get_json()
        if data["status"] in ("done", "error"):
            return data
        time.sleep(0.05)
    raise AssertionError("job no terminó a tiempo")


def test_xpa_requires_customer_column():
    client = _client()
    data = {
        "summarize_by": "xpa",
        "customer_column": "",
        "link_column": "B",
        "header_row": "1",
        "cloud_provider": "AWS",
    }
    data["excel_file"] = (io.BytesIO(b"dummy"), "in.xlsx")
    r = client.post("/process", data=data, content_type="multipart/form-data")
    assert r.status_code == 400
    assert "Customer" in r.get_json()["error"]


def test_xpa_download_returns_zip(monkeypatch):
    groups = {
        "Esfera": pd.DataFrame(
            [{"#": 1, "Provider": "AWS", "Instance": "m7i.large", "Quantity": 2}],
            columns=["#", "Provider", "Instance", "Quantity"],
        ),
        "UOL": pd.DataFrame(
            [{"#": 1, "Provider": "AWS", "Instance": "t3.medium", "Quantity": 5}],
            columns=["#", "Provider", "Instance", "Quantity"],
        ),
    }
    monkeypatch.setattr(flask_app, "process_excel_file", lambda *a, **k: groups)

    client = _client()
    data = {
        "summarize_by": "xpa",
        "customer_column": "A",
        "link_column": "B",
        "header_row": "1",
        "cloud_provider": "AWS",
    }
    data["excel_file"] = (io.BytesIO(b"dummy"), "in.xlsx")
    r = client.post("/process", data=data, content_type="multipart/form-data")
    assert r.status_code == 200
    job_id = r.get_json()["job_id"]

    status = _wait_done(client, job_id)
    assert status["status"] == "done", status

    dl = client.get(f"/download/{job_id}")
    assert dl.status_code == 200
    assert dl.mimetype == "application/zip"

    zf = zipfile.ZipFile(io.BytesIO(dl.data))
    names = sorted(zf.namelist())
    assert len(names) == 2
    assert any(n.startswith("Esfera_") and n.endswith(".xlsx") for n in names)
    assert any(n.startswith("UOL_") and n.endswith(".xlsx") for n in names)

    # cada archivo NO tiene fila de encabezado: la primera celda es el "#" = 1
    first = [n for n in names if n.startswith("Esfera_")][0]
    df = pd.read_excel(io.BytesIO(zf.read(first)), header=None)
    assert df.iloc[0, 0] == 1
    assert df.iloc[0, 1] == "AWS"
    assert df.shape[1] == 4


def test_non_xpa_still_returns_xlsx(monkeypatch):
    df = pd.DataFrame(
        [{"#": 1, "Provider": "AWS", "Instance": "t3.large", "Quantity": 1, "Company": "X"}]
    )
    monkeypatch.setattr(flask_app, "process_excel_file", lambda *a, **k: df)

    client = _client()
    data = {
        "summarize_by": "company",
        "customer_column": "A",
        "link_column": "B",
        "header_row": "1",
        "cloud_provider": "AWS",
    }
    data["excel_file"] = (io.BytesIO(b"dummy"), "in.xlsx")
    r = client.post("/process", data=data, content_type="multipart/form-data")
    job_id = r.get_json()["job_id"]
    _wait_done(client, job_id)

    dl = client.get(f"/download/{job_id}")
    assert dl.status_code == 200
    assert "spreadsheetml" in dl.mimetype
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_app_xpa.py -v`
Expected: FAIL — no existe la validación (el primer test obtiene 200 en vez de 400) y `/download`
no produce zip.

- [ ] **Step 3: Write minimal implementation**

3a. En `app.py`, añadir imports arriba (junto a los existentes):

```python
import zipfile
from datetime import date

from excel_processor import process_excel_file, xpa_filename, month_name_es
```

(Reemplaza la línea `from excel_processor import process_excel_file`.)

3b. En `process()`, tras leer `summarize_by` (después de la línea `summarize_by = ...`), agregar la
validación **antes** de crear el job:

```python
        if summarize_by == "xpa" and not customer_column:
            return jsonify({"error": "O modo Archivos XPA requer a coluna Customer configurada."}), 400
```

3c. En la inicialización del job (el `dict` dentro de `with _jobs_lock:`), agregar el campo `kind`:

```python
                "kind":     "xlsx",
```

3d. Dentro de `worker()`, reemplazar el bloque que arma el resultado (desde
`result_df = process_excel_file(...)` hasta `_jobs[job_id]["status"] = "done"`) por:

```python
            try:
                result = process_excel_file(
                    file_bytes, link_column, header_row, cloud_provider,
                    customer_column, summarize_by, on_progress
                )

                if summarize_by == "xpa":
                    out = io.BytesIO()
                    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
                        for company, df in result.items():
                            buf = io.BytesIO()
                            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                                df.to_excel(writer, index=False, header=False,
                                            sheet_name="Instâncias")
                            buf.seek(0)
                            zf.writestr(xpa_filename(company, date.today()), buf.getvalue())
                    out.seek(0)
                    with _jobs_lock:
                        _jobs[job_id]["result"] = out.getvalue()
                        _jobs[job_id]["kind"]   = "zip"
                        _jobs[job_id]["status"] = "done"
                else:
                    out = io.BytesIO()
                    with pd.ExcelWriter(out, engine="openpyxl") as writer:
                        result.to_excel(writer, index=False, sheet_name="Instâncias")
                    out.seek(0)
                    with _jobs_lock:
                        _jobs[job_id]["result"] = out.getvalue()
                        _jobs[job_id]["kind"]   = "xlsx"
                        _jobs[job_id]["status"] = "done"
                print(f"[worker] job {job_id} concluído.")
```

3e. Reemplazar `download()` por una versión que distinga `kind`:

```python
@app.route("/download/<job_id>")
def download(job_id):
    job = _jobs.get(job_id)
    if not job or job["status"] != "done" or not job["result"]:
        return jsonify({"error": "Resultado não disponível"}), 404

    if job.get("kind") == "zip":
        today = date.today()
        return send_file(
            io.BytesIO(job["result"]),
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"archivos_xpa_{today.year}_{month_name_es(today)}.zip",
        )

    return send_file(
        io.BytesIO(job["result"]),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="cloud_instances_verificadas.xlsx",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_app_xpa.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Run full suite (regresión)**

Run: `python -m pytest -v`
Expected: PASS (todo verde).

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_app_xpa.py
git commit -m "feat: app entrega zip de archivos XPA y valida columna Customer"
```

---

### Task 5: UI — quitar "Grand total", agregar "Archivos XPA"

**Files:**
- Modify: `templates/index.html` (bloque "Output type toggle", ~líneas 123-140)
- Test: `tests/test_template_radios.py`

**Interfaces:**
- Consumes: el JS existente lee `input[name="summarize"]:checked` (sin cambios).
- Produces: la página `/` contiene un radio `value="xpa"` y **no** contiene `value="total"`.

- [ ] **Step 1: Write the failing test**

Crear `tests/test_template_radios.py`:

```python
import app as flask_app


def test_index_has_xpa_radio_and_no_grand_total():
    flask_app.app.config["TESTING"] = True
    client = flask_app.app.test_client()
    html = client.get("/").get_data(as_text=True)
    assert 'value="xpa"' in html
    assert 'value="total"' not in html
    assert 'value="company"' in html
    assert 'value="none"' in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_template_radios.py -v`
Expected: FAIL — `value="total"` aún está presente y `value="xpa"` no existe.

- [ ] **Step 3: Write minimal implementation**

En `templates/index.html`, reemplazar el bloque del radio "Grand total":

```html
        <input type="radio" class="btn-check" name="summarize" id="sumTotal" value="total" />
        <label class="btn btn-outline-secondary" for="sumTotal">
          <i class="fas fa-sigma me-1"></i>Grand total
        </label>
```

por el radio "Archivos XPA":

```html
        <input type="radio" class="btn-check" name="summarize" id="sumXpa" value="xpa" />
        <label class="btn btn-outline-secondary" for="sumXpa">
          <i class="fas fa-file-zipper me-1"></i>Archivos XPA
        </label>
```

(Los radios "By company" y "Detailed" quedan igual; "By company" sigue siendo el `checked` por defecto.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_template_radios.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Run full suite + commit**

Run: `python -m pytest -v`
Expected: PASS (todo verde).

```bash
git add templates/index.html tests/test_template_radios.py
git commit -m "feat: UI cambia Grand total por Archivos XPA"
```

---

## Verificación final (manual, opcional)

- [ ] Ejecutar `python app.py`, abrir http://localhost:5000.
- [ ] Subir `ejemplos/COMPASS UOL - REPORT Q1-2026 LAUNCHED OPPORTUNITY BY QUARTER.xlsx`,
      configurar columnas (link `J`, customer `E`, header `6`), elegir **Archivos XPA**, procesar.
- [ ] Descargar el `.zip`, confirmar: un `.xlsx` por empresa, nombre `Empresa_2026_junio.xlsx`,
      4 columnas, **sin encabezado**, `#` desde 1.
- [ ] Confirmar que el botón "Grand total" ya no aparece.

---

## Self-Review (completado al escribir el plan)

- **Cobertura del spec:** quitar Grand total (Task 5), modo XPA con zip (Tasks 2-4), nombre
  `Empresa_Año_mes` (Task 1), 4 columnas sin encabezado (Tasks 2, 4), `#` por empresa (Task 2),
  saneo de nombre + empresa vacía (Task 1), requiere Customer (Task 4), sin resultados → zip vacío
  (Tasks 3-4), mes español minúscula (Task 1), rama `total` conservada en backend (no se toca).
- **Sin placeholders:** todos los pasos incluyen código/comando reales.
- **Consistencia de tipos:** `build_xpa_groups`/`process_excel_file(xpa)` devuelven `dict[str, DataFrame]`
  con columnas `["#","Provider","Instance","Quantity"]`; `xpa_filename(company, date)` usado en el
  worker; `kind` ∈ `{"xlsx","zip"}` consistente entre worker y `download`.
