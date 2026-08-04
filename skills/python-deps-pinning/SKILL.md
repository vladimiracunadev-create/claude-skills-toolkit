---
name: python-deps-pinning
description: >-
  Mide qué parte del árbol de dependencias Python de un repo es REALMENTE
  auditable por un scanner de vulnerabilidades, y nombra las que quedan fuera.
  Una dependencia declarada como `requests` o `requests>=2.0` no resuelve a una
  versión concreta, así que ningún scanner puede pronunciarse sobre ella y un "0
  vulnerabilidades" sobre esa superficie es un falso tranquilizante. Lee
  requirements*.txt, pyproject.toml (PEP 621, dependency-groups y Poetry) y
  detecta lockfiles (poetry.lock, uv.lock, Pipfile.lock, pdm.lock,
  requirements.lock). Reporta cobertura en porcentaje, lista las dependencias
  invisibles agrupadas por fichero, y da la receta de lockfile del gestor
  detectado. Úsalo cuando el usuario diga "pinea las dependencias", "por qué el
  scan no ve nada", "genera el lockfile", "las deps no están fijadas", "auditá
  las versiones de las dependencias", o antes/después de correr security-audit.
  Trabaja sobre `Path.cwd()` — funciona en cualquier repo Python.
---

# python-deps-pinning

Complemento directo de [`security-audit`](../security-audit/SKILL.md): ese skill
**declara** que las dependencias sin pin exacto quedan fuera del scan; este las
**cuantifica y las nombra**.

## Por qué existe

Un scanner de vulnerabilidades (OSV, GHSA, PyPA) responde a la pregunta *"¿la
versión X del paquete Y tiene CVEs?"*. Si el repo declara `requests` a secas, o
`requests>=2.0`, no hay versión X que consultar. La dependencia no es que salga
limpia: **es que nunca se miró**.

El resultado es un reporte que dice "0 vulnerabilidades" sobre una superficie
que jamás se auditó. Ese es el falso tranquilizante que este skill elimina:
convierte el silencio en un número.

---

## Cuándo invocar este skill

Triggers explícitos:

- "pinea las dependencias"
- "las deps no están fijadas"
- "genera el lockfile"
- "por qué el scan de seguridad no encuentra nada"
- "auditá las versiones de las dependencias"
- "pin dependencies" / "generate lockfile"

Triggers proactivos:

- Antes o después de correr `security-audit` (para interpretar su cobertura)
- Al añadir una dependencia nueva a `requirements.txt` o `pyproject.toml`
- Al preparar un release reproducible

---

## Cómo se invoca

```bash
python ~/.claude/skills/python-deps-pinning/python_deps_pinning.py                 # reporte
python ~/.claude/skills/python-deps-pinning/python_deps_pinning.py --strict        # exit 1 si hay invisibles
python ~/.claude/skills/python-deps-pinning/python_deps_pinning.py --threshold 90  # exit 1 si cobertura < 90%
python ~/.claude/skills/python-deps-pinning/python_deps_pinning.py --json          # salida JSON
```

---

## Cómo clasifica cada dependencia

| Estado | Ejemplo | ¿Auditable? | Motivo |
|---|---|---|---|
| `exact` | `requests==2.31.0` | ✅ | Resuelve a una versión concreta |
| `locked` | `requests>=2.0` **+ lockfile en el mismo directorio** | ✅ | El lockfile fija la versión real |
| `range` | `requests>=2.0` sin lockfile | ❌ | No resuelve: la instalación de hoy y la de mañana difieren |
| `bare` | `requests` | ❌ | Sin especificador alguno |
| `direct` | `pkg @ https://…`, `git+https://…`, `-e ./pkg` | ❌ | Fuera de todo índice consultable |

Un `==1.2.*` cuenta como rango, no como pin: el comodín no fija una versión.

La detección de lockfile es **conservadora**: solo cubre el manifest que vive
en su mismo directorio. Un `poetry.lock` en la raíz no se asume válido para un
`requirements.txt` de un subproyecto.

---

## Fuentes que lee

| Fichero | Qué extrae |
|---|---|
| `requirements*.txt` (recursivo) | Una dependencia por línea; ignora `-r`, `-c`, `--index-url`; marca `-e` como `direct` |
| `pyproject.toml` → `[project] dependencies` | PEP 621 |
| `pyproject.toml` → `[project] optional-dependencies` | Todos los grupos extra |
| `pyproject.toml` → `[dependency-groups]` | PEP 735 |
| `pyproject.toml` → `[tool.poetry.dependencies]` | Sintaxis de tablas de Poetry (excluye `python`) |

Lockfiles reconocidos: `poetry.lock`, `uv.lock`, `Pipfile.lock`, `pdm.lock`,
`requirements.lock`.

Excluye `node_modules`, `.venv`, `venv`, `vendor_py`, `site-packages`, `dist`,
`build`, `target` y cualquier directorio oculto.

---

## Qué NO hace / limitaciones

- **No modifica ningún fichero.** Es solo lectura: reporta y da la receta. No
  ejecuta `pip-compile` ni `poetry lock` por su cuenta — regenerar un lockfile
  cambia el árbol de dependencias y esa es una decisión del proyecto.
- **No consulta la red.** No resuelve versiones ni valida que existan en PyPI.
  Para eso está `security-audit`.
- **No lee el contenido del lockfile.** Comprueba su presencia junto al
  manifest; no verifica que esté sincronizado con él (un lockfile obsoleto
  cuenta como cobertura).
- **No cubre `setup.py`** con `install_requires` computado en Python: es código
  arbitrario, no un manifest declarativo.
- Solo Python. Para el resto del árbol de dependencias → `security-audit`.

---

## Dependencias

| Dependencia | Cómo instalar | Requerida u opcional |
|---|---|---|
| `python>=3.11` | viene con el SO | requerida (usa `tomllib`) |

Cero dependencias externas.

---

## Ejemplo de salida

```text
python-deps-pinning — repo: /repo

Manifests analizados: 2
  · requirements.txt
  · pyproject.toml

COBERTURA REAL DEL SCAN DE VULNERABILIDADES
  ----------------------------------------------------------
  dependencias declaradas   : 61
  resolubles a versión exacta: 0
  invisibles para el scanner : 61
  cobertura                  : 0.0%

FUERA DEL SCAN — un CVE en estas dependencias no se detectaría
  requirements.txt  (60)
    · flask                        rango sin lockfile
    · numpy                        rango sin lockfile
    … y 48 más

CÓMO CERRARLO
  pip-tools  → pip-compile requirements.in -o requirements.txt --generate-hashes
  uv         → uv pip compile requirements.in -o requirements.txt
```
