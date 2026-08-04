---
name: python-lint-guard
description: >-
  Gate de lint Python antes de commit/push, con control de PARIDAD toolchain —
  compara lo que el repo DECLARA (pyproject, ruff.toml, setup.cfg, .flake8,
  tox.ini, .pre-commit-config.yaml) contra lo que el CI REALMENTE ejecuta
  (.github/workflows), y detecta el caso que más commits de arreglo produce, el
  gate declarado cuyo hook local nunca se instaló. Si `ruff` está disponible,
  separa las violaciones MECÁNICAS (auto-corregibles) de las que exigen CRITERIO
  humano — nunca aplica `--fix` a ciegas sobre F841 o E402. Úsalo cuando el
  usuario diga "arregla el lint de Python", "corrige ruff", "por qué falla el
  lint en CI", "black rompió el CI", "valida los .py antes de pushear", o
  proactivamente después de editar cualquier `.py`. Trabaja sobre `Path.cwd()` —
  funciona en cualquier repo.
---

# python-lint-guard

El gemelo Python de [`md-lint-fix`](../md-lint-fix/SKILL.md): el gate que faltaba
en la cadena de guardias del toolkit.

## Por qué existe

Un `.py` modificado atravesaba `pre-commit-guard` y `pre-push-guard` **sin
lint**. Los dos guards encadenaban `yaml-control` + `md-lint-fix` + `pytest`, y
ninguno miraba el estilo del Python. El resultado observable son los commits
que solo existen para apagar un CI en rojo: `fix(lint): ruff F401/I001`,
`style: aplicar black para pasar CI`, `fix: wrap strings for ruff`.

Pero este skill **no es un wrapper de `ruff`**. Correr el linter es la parte
fácil y ya la hace el CI. Su aporte propio es la capa que ninguna herramienta
cubre: **la paridad entre lo declarado y lo ejecutado**.

---

## Cuándo invocar este skill

Triggers explícitos:

- "arregla el lint de Python"
- "corrige los errores de ruff"
- "por qué falla el lint en CI"
- "black rompió el CI"
- "valida los .py antes de pushear"
- "fix python lint"

Triggers proactivos:

- Después de editar cualquier `.py`
- Antes de `git commit` / `git push` con Python en el diff
- Cuando el CI falla en un job de lint y no está claro por qué en local pasaba

---

## Cómo se invoca

```bash
python ~/.claude/skills/python-lint-guard/python_lint_guard.py                # diff vs git
python ~/.claude/skills/python-lint-guard/python_lint_guard.py --all          # todos los .py
python ~/.claude/skills/python-lint-guard/python_lint_guard.py --fix          # auto-fix del set mecánico
python ~/.claude/skills/python-lint-guard/python_lint_guard.py --parity-only  # solo paridad, sin ruff
python ~/.claude/skills/python-lint-guard/python_lint_guard.py --json         # salida JSON
```

Exit code `0` si no hay errores, `1` si hay algo que bloquea commit/push.

---

## Capa 1 — Paridad de toolchain (núcleo, stdlib)

Cruza dos inventarios y reporta cuatro desalineaciones:

| Código | Qué detecta | Por qué importa |
|---|---|---|
| `PARITY-NO-CI` | Herramienta declarada que **ningún workflow ejecuta** | El gate no existe donde importa: nada impide que el código roto entre a `main` |
| `PARITY-NO-CONFIG` | El CI ejecuta una herramienta que el repo **no declara** | Config implícita: el dev no puede reproducir en local lo que el CI exige |
| `PARITY-CONFLICT` | Dos herramientas con **el mismo rol** (dos formateadores, dos linters) | Se pisan: cada una reescribe lo que la otra dejó, generando commits de ida y vuelta |
| `PARITY-HOOK-ABSENT` | Existe `.pre-commit-config.yaml` pero **el hook local no está instalado** | El caso más caro: el gate existe en el papel, no en la máquina. Cada violación se descubre en CI y cuesta un commit extra |
| `PARITY-NO-GATE` | Hay `.py` y **ningún linter** declarado ni en CI | Superficie sin cubrir |

Fuentes de declaración que lee: `pyproject.toml` (`[tool.*]` y dependencias),
`ruff.toml`, `.ruff.toml`, `setup.cfg`, `.flake8`, `tox.ini`,
`.pre-commit-config.yaml`. Fuente de ejecución: `.github/workflows/*.y*ml`,
mirando solo líneas `run:` / `uses:` para no confundir un comentario o el
nombre de un job con una ejecución real.

Herramientas reconocidas y su rol: `ruff` (linter+formatter), `black`,
`autopep8`, `yapf` (formatter), `flake8`, `pylint` (linter), `isort`
(import-sorter), `mypy` (type-checker).

---

## Capa 2 — Violaciones (opt-in, requiere `ruff`)

Si `ruff` no está instalado, esta capa se salta con un aviso `RUFF-ABSENT` y
la capa de paridad **ya se ejecutó igual**. Nunca falla por ausencia.

La aportación aquí es la separación en dos grupos:

**Mecánicas** — se corrigen sin criterio humano, y son las únicas que toca `--fix`:

`I001` · `F401` · `UP006` · `UP035` · `W291` · `W293` · `W391` · `RUF100` · `COM812` · `Q000`

**Requieren criterio** — se reportan, nunca se auto-corrigen:

| Regla | Por qué no se auto-corrige |
|---|---|
| `F841` | Variable asignada y nunca usada — **puede ser un bug real**, no basura |
| `E741` | Nombre ambiguo (`l`, `I`, `O`) — renombrar es decisión de diseño |
| `E402` | Import fuera del top — a veces es intencional (side-effects, `sys.path`) |
| `E501` | Línea demasiado larga — la arregla el formateador, no el linter |
| `S110` / `S112` | `try-except-pass` / `continue` — silenciar excepciones puede ocultar fallos |
| `C901` | Complejidad excesiva — exige refactor, no un fix |
| `B008` | Llamada en el default de un argumento — semántica, no estilo |

`--fix` invoca `ruff check --select <set-mecánico> --fix`. **Nunca** un `--fix`
global: eso es exactamente lo que borra la evidencia de un bug al eliminar la
variable que lo delataba.

---

## Qué NO hace / limitaciones

- **No formatea.** No invoca `black` ni `ruff format`. Reporta el conflicto si
  hay dos formateadores, pero la decisión de cuál usar es del proyecto.
- **No instala nada.** Si falta `ruff` o el hook de `pre-commit`, lo dice y da
  el comando; no lo ejecuta por su cuenta.
- **La detección en workflows es textual**, no semántica: un `run:` que invoque
  el linter a través de un `Makefile` o un script propio puede no detectarse.
  Falso negativo posible en `PARITY-NO-CI` — nunca falso positivo silencioso.
- **No juzga la configuración** del linter (qué reglas activar es del proyecto).
- Solo Python. Para YAML → [`yaml-control`](../yaml-control/SKILL.md); para
  Markdown → [`md-lint-fix`](../md-lint-fix/SKILL.md).

---

## Dependencias

| Dependencia | Cómo instalar | Requerida u opcional |
|---|---|---|
| `python>=3.11` | viene con el SO | requerida (usa `tomllib`) |
| `git` | — | opcional (sin git analiza todo el árbol) |
| `ruff` | `pip install ruff` | **opcional** — capa 2; degrada con aviso |
| `pre-commit` | `pip install pre-commit` | opcional — solo para aplicar la recomendación |

---

## Integración con los guards

Ambos guards del toolkit lo invocan automáticamente cuando hay `.py` en el diff:

- [`pre-commit-guard`](../pre-commit-guard/SKILL.md) → `--parity-only` sobre lo *staged* (rápido, < 2 s)
- [`pre-push-guard`](../pre-push-guard/SKILL.md) → análisis completo sobre el diff vs `origin/<branch>`

Si el skill no está instalado, ambos guards lo saltan con `⊘` y siguen.

---

## Ejemplo de salida

```text
python-lint-guard — repo: C:\dev\social-bot-scheduler
  ficheros .py en scope: 47

Toolchain declarado vs. ejecutado en CI
  ---------------------------------------------------------------------
  herramienta   rol               declarado en             CI
  black         formatter         .pre-commit-config.yaml  ci-cd.yml
  flake8        linter            .pre-commit-config.yaml  ci-cd.yml
  mypy          type-checker      pyproject.toml           ci-cd.yml

ERRORES
  ✗ [PARITY-HOOK-ABSENT] .pre-commit-config.yaml existe pero el hook local NO está instalado
      → instálalo con `pre-commit install` — sin él el linter solo corre en CI
        y cada violación cuesta un commit extra de arreglo

❌ Hay errores que bloquean commit/push.
```
