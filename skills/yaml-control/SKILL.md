---
name: yaml-control
description: Valida archivos YAML (sintaxis + estructura) y workflows de GitHub Actions (actionlint) antes de commit/push. Úsalo cuando el usuario diga "valida los yaml", "revisa los workflows", "lint yaml", "actionlint", "errores de github actions", o "antes de pushear los workflows". También úsalo proactivamente cuando edites archivos en `.github/workflows/`, `compose.yml`, `pyproject` con secciones YAML, o cualquier `*.yml` / `*.yaml` modificado en el repo actual.
---

# yaml-control

Detecta y reporta errores en archivos YAML antes de pushear. Cubre tres capas:

1. **Sintaxis YAML** (`python -c "import yaml; yaml.safe_load(...)"`).
2. **Estructura GitHub Actions** (`actionlint` — sintaxis específica de workflows + shellcheck embebido).
3. **Convenciones del repo** — versiones de actions pinneadas a SHA (`uses: org/action@<40-char-sha>`), permisos explícitos en cada workflow, `fail-fast: false` en matrices grandes.

---

## Cuándo usar este skill

- El usuario menciona "errores de yaml", "valida yaml", "actionlint", "los workflows fallan", "github actions error".
- Antes de cualquier `git push` que toque `.github/workflows/*.yml`.
- Después de editar `compose.yml`, `docker-compose.yml`, o secciones YAML de un proyecto.
- Cuando un PR está rojo y la causa es el parser de Actions (`Invalid workflow file`, `missing required property`).
- Proactivamente: si en la sesión actual editaste un `*.yml` o `*.yaml`, ejecuta este skill antes de commitear.

---

## Cómo se invoca

Sin argumentos: valida los YAML modificados según `git status` (uso normal pre-push).

```bash
python ~/.claude/skills/yaml-control/yaml_control.py
```

Modos:

```bash
# Todos los YAML del repo actual (incluye no modificados)
python ~/.claude/skills/yaml-control/yaml_control.py --all

# Solo diagnóstico, sin instalar nada
python ~/.claude/skills/yaml-control/yaml_control.py --dry-run

# Solo workflows (.github/workflows/)
python ~/.claude/skills/yaml-control/yaml_control.py --workflows

# Verbose — muestra cada archivo verificado
python ~/.claude/skills/yaml-control/yaml_control.py -v
```

Trabaja siempre en `Path.cwd()` — no importa desde qué carpeta se llame.

---

## Qué valida exactamente

### Capa 1 — sintaxis YAML

- Parsing con `yaml.safe_load`. Falla si hay:
  - Indentación inconsistente.
  - Llaves/corchetes sin cerrar.
  - Anchors o aliases mal formados.
  - BOM UTF-8 al inicio (causa de errores misteriosos en Actions runner).
  - Tab characters (YAML exige espacios).

### Capa 2 — workflows GitHub Actions (`actionlint`)

Sólo se ejecuta si el archivo está en `.github/workflows/`.

- Sintaxis específica del schema de workflows (`on:`, `jobs:`, `steps:`, etc.).
- `shellcheck` embebido para los `run:` bash (catches `set -e` problemas, var unquoted, etc.).
- Validación de expresiones `${{ ... }}` (referencias a inputs/secrets/matrix inexistentes).
- Validación de `uses:` (action existe, version sintácticamente válida).

### Capa 3 — convenciones del repo

- **Actions con SHA pinneado**: `uses: actions/checkout@<sha>` no `@v4`. Catches:
  ```yaml
  - uses: actions/checkout@v4   # ❌ warning
  - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # ✅
  ```
- **Permisos explícitos**: cada workflow debe declarar `permissions: ...` a nivel root.
- **`fail-fast: false`** en matrices con más de 5 elementos (para que un fallo no cancele el resto).

---

## Instalación de `actionlint`

Si `actionlint` no está en PATH, el skill avisa y sugiere:

```bash
# Windows (PowerShell)
winget install rhysd.actionlint

# O directamente el binario (Linux/Mac)
bash <(curl -s https://raw.githubusercontent.com/rhysd/actionlint/main/scripts/download-actionlint.bash)
```

Si `actionlint` no está disponible, sigue con sólo las capas 1 y 3 y reporta:
> ⚠ actionlint no instalado — saltando validación de schema de workflows.

---

## Salida esperada

```
YAML control — repo: C:/dev/langgraph-realworld
  scope: 3 archivos modificados (.github/workflows/ci.yml, .github/workflows/security.yml, cases/22-.../compose.yml)

[1/3] .github/workflows/ci.yml
  ✓ sintaxis YAML
  ✓ actionlint
  ⚠ Convenciones: 2 actions sin SHA pinneado
    - actions/checkout@v4 (línea 16) — debería ser @<sha>
    - actions/setup-python@v5 (línea 19) — debería ser @<sha>

[2/3] .github/workflows/security.yml
  ✓ sintaxis YAML
  ✓ actionlint
  ✓ convenciones

[3/3] cases/22-.../compose.yml
  ✓ sintaxis YAML
  - actionlint omitido (no es workflow)
  - convenciones omitidas (no es workflow)

Resumen: 2 warnings, 0 errores. OK para push.
```

Si hay errores (no warnings), exit 1 → bloquea el push si se usa en pre-push hook.

---

## Errores comunes detectados

| Patrón | Capa | Mensaje típico |
|---|---|---|
| Tabs en YAML | 1 | `found character '\t' that cannot start any token` |
| BOM al inicio | 1 | `mapping values are not allowed here` |
| `uses: actions/checkout@v4` | 3 | `action no pinneada a SHA` |
| `runs-on` sin valor | 2 actionlint | `property "runs-on" is required` |
| Matriz grande sin `fail-fast: false` | 3 | `matrix de N>5 sin fail-fast: false` |
| `${{ matrix.x }}` con `x` no declarada | 2 actionlint | `matrix value "x" is not defined` |
| `run:` con `cd && cmd` sin pipefail | 2 (shellcheck) | `SC2154`, `SC2086`, etc. |

---

## Integración con flujo de trabajo

**Recomendado**: invocar antes de cada `git push` que toque `.yml` / `.yaml`.

```bash
# Si edité workflows
python ~/.claude/skills/yaml-control/yaml_control.py
git push
```

**Combinable con [[md-lint-fix]]**: el agente puede invocar ambos seguidos antes de pushear cambios mixtos (markdown + yaml).
