---
name: pre-push-guard
description: Orquestador que corre los validadores del toolkit sobre los archivos del diff (vs `origin/<branch>`) antes de un `git push` — encadena yaml-control sobre los `*.y*ml` modificados, md-lint-fix en modo check sobre los `*.md` modificados, y `pytest` si el diff toca `.py` y existe `tests/`. Aborta el push (exit 1) si algún paso falla, con un reporte unificado en stdout. Úsalo cuando el usuario diga "valida antes de pushear", "chequea todo antes del push", "pre-push", "guard antes de push", "corre todos los checks", "lint completo antes de subir", o proactivamente justo antes de invocar `git push`. Soporta `--install-hook` para registrarlo como git pre-push hook (opt-in, nunca automático). Trabaja sobre `Path.cwd()`.
---

# pre-push-guard

Un **único comando** que ejecuta toda la suite de validación local del toolkit sobre los archivos modificados — para evitar que llegue a CI un push que ya se sabía roto.

Es un **orquestador**: no duplica lógica de [[yaml-control]], [[md-lint-fix]] ni de los tests. Los invoca en orden, sobre el diff real (`git diff --name-only origin/<branch>...HEAD` + working tree), y agrega los resultados.

---

## Cuándo invocar este skill

Triggers explícitos:

- "valida antes de pushear"
- "chequea todo antes del push"
- "pre-push"
- "guard antes de push"
- "corre todos los checks"
- "lint completo antes de subir"

Triggers proactivos:

- Justo antes de ejecutar `git push` cuando hay cambios sin pushear.
- Cuando el usuario menciona que "CI estuvo rojo por X" y X es lint/tests — invocar pre-push-guard antes del siguiente push.

---

## Cómo se invoca

```bash
python ~/.claude/skills/pre-push-guard/pre_push_guard.py
```

Modos:

```bash
# Todos los archivos rastreados (no solo el diff)
python .../pre_push_guard.py --all

# Saltar tests (solo lint)
python .../pre_push_guard.py --no-tests

# Saltar lint (solo tests)
python .../pre_push_guard.py --no-lint

# Output JSON
python .../pre_push_guard.py --json

# Instalar como git hook (opt-in)
python .../pre_push_guard.py --install-hook

# Desinstalar el hook
python .../pre_push_guard.py --uninstall-hook
```

**Importante**: el hook NO se instala automáticamente. Hay que pasar `--install-hook` explícitamente.

Exit codes:

- `0` — todos los checks pasaron.
- `1` — al menos un check falló → bloquea el push.
- `2` — error de invocación (no es un repo git, etc.).

---

## Qué hace exactamente, en orden

```text
1. Detecta el diff:
   git diff --name-only origin/<current-branch>...HEAD
   + git diff --name-only HEAD       (cambios staged + unstaged)
   + git ls-files --others --exclude-standard  (archivos nuevos)

2. Particiona el diff por extensión:
   - *.yml / *.yaml  → yaml-control
   - *.md            → md-lint-fix --check
   - *.py            → trigger para pytest si existe tests/

3. Ejecuta los pasos en orden, abortando al primer error:
   [a] yaml-control sobre los YAML del diff
   [b] md-lint-fix --check sobre los .md del diff (no auto-fix — solo reporta)
   [c] pytest si hay .py en el diff y existe tests/

4. Reporta resumen unificado con:
   - cuántos archivos vio cada step
   - cuánto tardó cada uno
   - qué falló y cómo arreglarlo
```

---

## Qué NO hace / limitaciones

- **No hace auto-fix**. Por diseño — la idea es bloquear, no modificar. Si quieres auto-fix de markdown, corre `md-lint-fix` por separado antes.
- **No instala dependencias**. Si `pytest` no está en el entorno y hay `.py` en el diff, te avisa y aborta. No instala silenciosamente nada.
- **No reemplaza CI**. Es un *pre-flight check*, no la verdad. CI sigue siendo la fuente de verdad.
- **No corre security-audit**. Audit es pesado y opt-in. Si quieres incluirlo, invócalo a mano.
- **El hook git ignora `--no-tests` / `--no-lint`**. El hook siempre corre la suite completa — esos flags solo aplican a invocación manual.

---

## Dependencias

| Dependencia | Cómo instalar | Requerida o opcional |
|---|---|---|
| `python>=3.11` | viene con el SO | requerida |
| `git` | sistema | requerida |
| `~/.claude/skills/yaml-control/` | parte del toolkit | opcional (si falta, salta capa YAML) |
| `~/.claude/skills/md-lint-fix/` | parte del toolkit | opcional (si falta, salta capa MD) |
| `pytest` | `pip install pytest` | opcional (si falta y hay `.py`, avisa) |

Si los skills hermanos no están instalados, `pre-push-guard` degrada con un warning explícito — no falla.

---

## Ejemplos de salida

### Caso OK

```text
pre-push-guard — repo: C:/dev/claude-skills-toolkit
  rama: main · base: origin/main
  diff: 4 archivos (.github/workflows/ci.yml, README.md, skills/foo/main.py, tests/test_foo.py)

[1/3] yaml-control · 1 archivo
  ✓ .github/workflows/ci.yml
  (0.8s)

[2/3] md-lint-fix --check · 1 archivo
  ✓ README.md
  (0.3s)

[3/3] pytest · 8 tests
  ✓ 8 passed
  (1.2s)

✅ Todo verde. OK para `git push` (2.3s total).
```

Exit `0`.

### Caso con falla

```text
pre-push-guard — repo: C:/dev/foo
  rama: feat/auth · base: origin/main
  diff: 3 archivos (compose.yml, src/auth.py, tests/test_auth.py)

[1/3] yaml-control · 1 archivo
  ✗ compose.yml — sintaxis YAML inválida (línea 14)
  (0.4s)

❌ Bloqueado en step [1/3]. Arregla y vuelve a intentar.
   Detalles arriba ↑
```

Exit `1`. No corre los pasos siguientes — fail-fast.

---

## Instalación como git hook

```bash
cd /tu/repo
python ~/.claude/skills/pre-push-guard/pre_push_guard.py --install-hook
```

Esto crea `.git/hooks/pre-push` (o lo respalda si ya existe como `.pre-push.bak`). El hook llama al skill antes de cada `git push`. Si falla, el push se aborta.

Para desinstalar:

```bash
python ~/.claude/skills/pre-push-guard/pre_push_guard.py --uninstall-hook
```

Restaura el backup si existe; si no, elimina el hook.

El hook se puede saltar con `git push --no-verify` (estándar de git) en caso de emergencia.

---

## Integración con otros skills

```text
[[yaml-control]]   — la capa 1
[[md-lint-fix]]    — la capa 2 (modo check)
[[security-audit]] — NO incluido (demasiado pesado para pre-push)
```
