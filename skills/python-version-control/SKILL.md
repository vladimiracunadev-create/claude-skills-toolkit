---
name: python-version-control
description: Audita la coherencia de versión de Python en un repositorio (pyproject.toml requires-python + classifiers + target-version de ruff/mypy/black, Dockerfile FROM, .github/workflows/*.yml setup-python, .python-version, runtime.txt, tox.ini, noxfile.py, pre-commit). Detecta drift entre las fuentes y propone una versión canónica. Úsalo cuando el usuario diga "audita versión python", "coherencia python version", "drift python", "qué versión python usa el repo", "revisa python version", "python version control", o proactivamente al editar pyproject.toml, Dockerfile, o workflows con setup-python. Trabaja sobre Path.cwd() — funciona en cualquier repo. Solo lectura por defecto; aplica fixes solo con --fix y confirmación del usuario.
---

# python-version-control

Audita y reporta la coherencia de versión de Python declarada en distintos lugares de un repositorio. Resuelve el problema típico:

> "El CI corre 3.10, el Dockerfile usa 3.11, ruff apunta a `py310`, pero la documentación dice 'Python 3.12+'."

Drift así rompe en silencio: la clase enseña features de 3.12, el CI con 3.10 las rechaza, el contenedor de prod corre 3.11 con bugs específicos.

---

## Cuándo usar este skill

- El usuario dice: "audita la versión de python", "revisa python version", "drift python", "coherencia python", "qué versión usa este repo", "python version control".
- Proactivamente: cuando en la sesión actual se editó `pyproject.toml`, `Dockerfile*`, `compose*.y*ml`, `.github/workflows/*.yml` con `setup-python`, `.python-version`, `runtime.txt`, `tox.ini`, `noxfile.py`, o `.pre-commit-config.yaml`.
- Antes de bumpear la versión de Python en algún archivo (para entender qué más hay que tocar).
- Después de un fallo de CI por sintaxis incompatible (`SyntaxError` que solo aparece en una versión del matrix).

---

## Cómo se invoca

Sin argumentos: corre el scan sobre `Path.cwd()` y reporta drift.

```bash
python ~/.claude/skills/python-version-control/scan.py
```

Con argumento `--fix <version>` (e.g. `--fix 3.12`): muestra qué cambios haría para alinear todo a esa versión, **sin escribir**. Aplica cambios solo si el usuario confirma explícitamente.

```bash
python ~/.claude/skills/python-version-control/scan.py --fix 3.12
```

Argumento `--json`: salida estructurada (útil para integrarlo en otros skills como `pre-push-guard`).

---

## Qué detecta (fuentes de verdad)

| Fuente | Campo | Ejemplo |
|---|---|---|
| `pyproject.toml` | `[project] requires-python` | `">=3.10"` |
| `pyproject.toml` | `[project] classifiers` | `"Programming Language :: Python :: 3.12"` |
| `pyproject.toml` | `[tool.ruff] target-version` | `"py310"` |
| `pyproject.toml` | `[tool.mypy] python_version` | `"3.12"` |
| `pyproject.toml` | `[tool.black] target-version` | `["py310"]` |
| `setup.py` / `setup.cfg` | `python_requires` | legacy |
| `Dockerfile*` | `FROM python:X.Y` | `python:3.11.10-slim` |
| `Dockerfile*` | `ARG PYTHON_VERSION` | `3.11` |
| `compose*.y*ml` | `image: python:X.Y` o build args | derivado |
| `.github/workflows/*.yml` | `actions/setup-python` `with.python-version` | scalar o matrix |
| `.python-version` | contenido | `3.12.1` (pyenv) |
| `runtime.txt` | contenido | `python-3.11.10` (Heroku/Procfile) |
| `tox.ini` | `envlist`, `[testenv:pyXY]` | `py310, py311` |
| `noxfile.py` | `@nox.session(python=...)` | lista de versiones |
| `.pre-commit-config.yaml` | `default_language_version: python: ...` | `python3.12` |
| `README.md` | menciones tipo `Python 3.X` (informativo, no bloqueante) | badges/texto |

---

## Output

Tabla con cada source, versión(es) declarada(s), y flag de drift:

```
Fuente                                       Versión          Estado
─────────────────────────────────────────────────────────────────────
pyproject.toml  requires-python              >=3.10           ⚠ floor 3.10
pyproject.toml  ruff target-version          py310            ⚠ desfasado vs Docker
pyproject.toml  classifiers                  3.10, 3.11, 3.12 OK rango
Dockerfile      FROM                         3.11.10          ⚠ no es el target
.github/workflows/ci.yml matrix              3.10, 3.11, 3.12 OK
.github/workflows/deploy-pages.yml           3.12             OK (script run)
.github/workflows/security.yml               3.11             ⚠ inconsistente
.python-version                              (no existe)      —
README.md menciones                          3.12+            ⚠ pyproject permite 3.10

VERDICT: drift detectado (5 fuentes consistentes, 4 desalineadas)
Sugerencia: alinear a 3.12 (la más reciente declarada como soportada en
            README/clases) o a 3.10 (la mínima común). Revisa qué features
            usas para decidir.
```

---

## Cómo aplicar fixes

**Importante: cero auto-fix sin confirmación del usuario.** El skill puede *proponer* el diff exacto que aplicaría, pero el usuario debe decir "aplica" antes de tocar archivos.

Flow:
1. Skill detecta drift → reporta tabla.
2. Usuario dice "alinea a 3.12" o `--fix 3.12`.
3. Skill genera diff propuesto (sin aplicar).
4. Usuario confirma → aplicar.
5. Reporte de qué se cambió + recomendación de re-correr CI.

**Reglas para el target:**
- `requires-python` se actualiza a `>=X.Y` (mantiene operador `>=`)
- `classifiers` se sincronizan al rango entre el min de `requires-python` y la última versión del CI matrix
- `target-version` de ruff/mypy/black se alinea al **mínimo** declarado (no al target ideal, sino al piso, para que el formateo no use features no disponibles)
- `Dockerfile FROM` usa la **major.minor** del target principal (no patch, deja al runtime resolver el patch más reciente)
- workflows `setup-python` se alinean según rol:
  - CI matrix: rango del min al max declarado en `requires-python`/classifiers
  - Deploy/Security: una sola versión, la del target principal

---

## Cuándo NO usar este skill

- Repos non-Python (sin `pyproject.toml`, `setup.py`, ni `requirements.txt`)
- Cuando el usuario está activamente bumpeando una sola versión y sabe lo que hace
- Para temas de dependencias específicas (eso lo cubre security-audit o un dep-check separado)

---

## Integración con otros skills

- **pre-push-guard**: puede invocar este skill (modo `--json`) si el diff toca archivos relevantes.
- **security-audit**: complementario — security-audit revisa CVEs de dependencias, este skill revisa la versión del *intérprete*.
- **yaml-control**: si los workflows tienen drift, este skill lo detecta; yaml-control valida sintaxis. Ortogonales.
