---
name: pre-commit-guard
description: Orquestador que corre yaml-control y md-lint-fix --dry-run sobre los archivos staged (`git diff --cached`) antes de un `git commit`. Complementa pre-push-guard con una capa más rápida y temprana — bloquea commits con YAML inválido o Markdown roto antes de que entren al historial local. No corre pytest (para mantenerlo < 2s en el caso típico). Aborta el commit (exit 1) si algún paso falla, con reporte unificado en stdout. Úsalo cuando el usuario diga "valida antes de commitear", "chequea antes del commit", "pre-commit", "guard antes de commit", "lint antes de commit", "instala pre-commit hook", o proactivamente justo antes de invocar `git commit`. Soporta `--install-hook` para registrarlo como git pre-commit hook (opt-in, nunca automático). Trabaja sobre `Path.cwd()`.
---

# pre-commit-guard

Un **único comando** que valida los archivos **staged** contra las reglas del toolkit antes de que entren al historial. Es el gemelo rápido de `pre-push-guard`.

Es un **orquestador**: no duplica lógica de [[yaml-control]] ni de [[md-lint-fix]]. Los invoca sobre el diff staged (`git diff --cached --name-only`) y agrega los resultados.

---

## Por qué existe (y por qué no basta con pre-push-guard)

`pre-push-guard` ya cubría la línea de defensa "antes de compartir con otros". Pero el commit y el push suceden en momentos distintos:

| | pre-commit-guard | pre-push-guard |
|---|---|---|
| ⏱️ Cuándo dispara | Cada `git commit` | Cada `git push` |
| 🎯 Alcance | Solo staged (lo que entra al commit) | Diff vs `origin/<branch>` + working tree |
| 🧪 Corre pytest | **No** — solo lint | Sí (si hay `.py` + `tests/`) |
| ⚡ Objetivo de tiempo | < 2s | < 30s |
| 🛑 Qué bloquea | Que un commit **malformado entre al historial** | Que se **comparta** con otros |

Sin `pre-commit-guard` un YAML roto entra al historial local; hay que arreglarlo con `git commit --amend` o rebase. Con este skill el commit se aborta antes: arregla, `git add`, reintenta.

---

## Cuándo invocar este skill

Triggers explícitos:

- "valida antes de commitear"
- "chequea antes del commit"
- "pre-commit"
- "guard antes de commit"
- "lint antes de commit"
- "instala pre-commit hook"

Triggers proactivos:

- Justo antes de `git commit` cuando hay archivos staged y alguno es `.yml`/`.yaml`/`.md`.
- Después de que el usuario tuvo que hacer `git commit --amend` por un lint error obvio.

---

## Cómo se invoca

```bash
python ~/.claude/skills/pre-commit-guard/pre_commit_guard.py
```

Modos:

```bash
# Todos los archivos rastreados (útil para validar el repo entero)
python .../pre_commit_guard.py --all

# Output JSON (integrable con otros skills)
python .../pre_commit_guard.py --json

# Instalar como git hook (opt-in)
python .../pre_commit_guard.py --install-hook

# Desinstalar el hook
python .../pre_commit_guard.py --uninstall-hook
```

**Importante:** el hook NO se instala automáticamente. Hay que pasar `--install-hook` explícitamente.

Exit codes:

- `0` — todos los checks pasaron.
- `1` — al menos un check falló → bloquea el commit.
- `2` — error de invocación (no es un repo git, etc.).

---

## Qué hace exactamente, en orden

```text
1. Detecta staged files:
   git diff --cached --name-only --diff-filter=ACMR
   (solo lo que va al próximo commit — no incluye working tree ni untracked)

2. Particiona por extensión:
   - *.yml / *.yaml  → yaml-control
   - *.md            → md-lint-fix --dry-run

3. Ejecuta los pasos en orden, abortando al primer error:
   [a] yaml-control sobre los YAML staged
   [b] md-lint-fix --dry-run sobre los .md staged (no auto-fix)

4. Reporta resumen unificado con archivos vistos, tiempo por paso,
   y qué falló.
```

---

## Qué NO hace / limitaciones

- **No corre pytest.** Por diseño — pre-commit debe ser rápido. Para tests, usa [[pre-push-guard]].
- **No hace auto-fix.** Bloquea, no modifica. Si quieres auto-fix de Markdown, `md-lint-fix` por separado antes de re-stagear.
- **No instala dependencias.** Si un skill hermano no está en `~/.claude/skills/`, se salta con warning explícito.
- **Solo valida lo staged.** Archivos modificados pero no `git add`-eados no entran al análisis (a menos que uses `--all`).
- **No reemplaza CI.** Es un *pre-flight check*, no la verdad. CI sigue siendo la fuente autoritativa.

---

## Dependencias

| Dependencia | Cómo instalar | Requerida o opcional |
|---|---|---|
| `python>=3.11` | viene con el SO | requerida |
| `git` | sistema | requerida |
| `~/.claude/skills/yaml-control/` | parte del toolkit | opcional (si falta, salta capa YAML) |
| `~/.claude/skills/md-lint-fix/` | parte del toolkit | opcional (si falta, salta capa MD) |

Si los skills hermanos no están instalados, `pre-commit-guard` degrada con un warning explícito — no falla.

---

## Ejemplos de salida

### Caso OK

```text
pre-commit-guard — repo: C:/dev/mi-proyecto
  staged: 2 archivo(s) (.github/workflows/ci.yml, README.md)

[1/2] yaml-control · 1 archivo(s)
  ✓ OK (0.4s)

[2/2] md-lint-fix --dry-run · 1 archivo(s)
  ✓ OK (0.3s)

✅ Todo verde. OK para `git commit` (0.7s total).
```

Exit `0`.

### Caso con falla

```text
pre-commit-guard — repo: C:/dev/foo
  staged: 2 archivo(s) (compose.yml, notes.md)

[1/2] yaml-control · 1 archivo(s)
  ✗ FALLÓ (0.4s)
    compose.yml — sintaxis YAML inválida (línea 14)

❌ Bloqueado en step [1/2]. Arregla y vuelve a intentar (o `git commit --no-verify` en emergencia).
```

Exit `1`. No corre los pasos siguientes — fail-fast.

---

## Instalación como git hook

```bash
cd /tu/repo
python ~/.claude/skills/pre-commit-guard/pre_commit_guard.py --install-hook
```

Esto crea `.git/hooks/pre-commit` (o lo respalda como `.pre-commit.bak` si ya existía). El hook corre el skill antes de cada `git commit`. Si falla, el commit se aborta.

Para desinstalar:

```bash
python ~/.claude/skills/pre-commit-guard/pre_commit_guard.py --uninstall-hook
```

Restaura el backup si existe; si no, elimina el hook.

El hook se puede saltar con `git commit --no-verify` (estándar de git) en emergencia — mismo escape hatch que `pre-push-guard`.

---

## Recomendado: instalar ambos hooks

Los dos skills se complementan sin solaparse:

```bash
python ~/.claude/skills/pre-commit-guard/pre_commit_guard.py --install-hook
python ~/.claude/skills/pre-push-guard/pre_push_guard.py --install-hook
```

Resultado — dos líneas de defensa progresivas:

- **En cada commit** → lint rápido sobre lo staged (< 2s)
- **En cada push** → lint completo + tests sobre el diff vs origin (< 30s)

Los tiempos son aditivos pero el commit-side es el que se ejecuta muchas más veces, así que mantenerlo liviano paga.

---

## Integración con otros skills

```text
[[yaml-control]]    — la capa 1
[[md-lint-fix]]     — la capa 2 (modo dry-run/check)
[[pre-push-guard]]  — hermano mayor: añade pytest, corre en push
[[security-audit]]  — NO incluido (demasiado pesado para pre-commit)
```
