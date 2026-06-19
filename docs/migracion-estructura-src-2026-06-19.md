# Migración de estructura a `src/` — 2026-06-19

Registro temporal para poder revertir los cambios de ubicación si algo falla.
Bórralo una vez verificado que todo funciona en uso real.

## Objetivo

Ajustar el repo a las reglas de ubicación de carpetas: el código fuente Python pasa a
`src/`. Los scripts de arranque/instalación (`run.bat`, `install.bat`) se mantienen en la
raíz (excepción acordada y reflejada en las reglas globales).

## Cambios realizados

### Movimientos (con `git mv`, historial preservado)

| Antes (raíz) | Después |
|---|---|
| `app.py` | `src/app.py` |
| `aws_calculator.py` | `src/aws_calculator.py` |
| `excel_processor.py` | `src/excel_processor.py` |
| `templates/` | `src/templates/` |

`templates/` se mueve junto a `app.py` para que Flask siga resolviéndolo vía
`__file__` sin tocar código.

### Archivos nuevos

- `tests/conftest.py`: inserta `src/` en `sys.path` para que las pruebas importen
  `app`, `excel_processor` y `aws_calculator` por nombre. Se ubica en `tests/` (no en la
  raíz) para no dejar ningún `.py` en la raíz del proyecto.

### Archivos editados

- `run.bat`: `python app.py` → `python src\app.py`; se añadió `cd /d "%~dp0"`.
- `README.md`: sección "Estructura del proyecto" y comando de desarrollo
  (`python src/app.py`).
- `CLAUDE.md`: sección "Estructura del proyecto" y comando de desarrollo.

### Sin cambios

- `install.bat`: `requirements.txt` sigue en la raíz.
- Código Python: ningún cambio de lógica ni de rutas internas (Flask resuelve templates
  por `__file__`; los imports funcionan con `src/` en el path).

## Verificación

- `python -m pytest -q` → 16 pruebas en verde.
- Smoke test: `import app`, `GET /` → 200, `template_folder` resuelto.

## Cómo revertir

Si el repo aún no se ha commiteado, deshacer los movimientos y archivos:

```sh
git mv src/app.py app.py
git mv src/aws_calculator.py aws_calculator.py
git mv src/excel_processor.py excel_processor.py
git mv src/templates templates
git checkout -- run.bat README.md CLAUDE.md
rm tests/conftest.py
rm docs/migracion-estructura-src-2026-06-19.md
```

Si ya hay un commit con la migración, basta con revertirlo:

```sh
git revert <hash-del-commit-de-migracion>
```
