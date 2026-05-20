# 🤝 Contribuir

¡Gracias por considerar contribuir! Este repo busca acumular skills **útiles, generales y mantenidos**. Lo que sigue es la guía mínima para que tu PR pase rápido por review.

[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-2da44e?logo=github)](https://github.com/vladimiracunadev-create/claude-skills-toolkit/pulls)
[![Code of Conduct](https://img.shields.io/badge/Code%20of-Conduct-4baaaa)](CODE_OF_CONDUCT.md)

---

## 📜 Reglas para un skill nuevo

1. **Autónomo.** No asume paths absolutos al sistema del autor. Si el script necesita el repo del usuario, usa `Path.cwd()`.
2. **`SKILL.md` con frontmatter completo.** Campos obligatorios: `name`, `description`. El `description` debe incluir los triggers en español **y** en inglés.
3. **Cero dependencias por defecto.** Si necesita una herramienta externa: docúmentalo en `SKILL.md` y degrada gracefully cuando no esté.
4. **Cross-platform** o limitación explícita (ej. *"requiere bash"*).
5. **Honestidad.** Documenta qué **NO** hace y qué riesgos tiene. Un skill que oculta sus límites es peor que un skill que no existe.

---

---

## 🔄 Workflow

### 1. Clona el template

```bash
cp -r skills/_template skills/mi-skill
```

### 2. Edita `skills/mi-skill/SKILL.md`

- Cambia `name`, `description` (incluyendo triggers).
- Documenta cuándo usar / cuándo NO usar.
- Lista limitaciones y dependencias.

### 3. Implementa el script

`skills/mi-skill/<nombre>.py` o `.sh`. Sigue las convenciones de la sección [Estilo](#estilo).

### 4. Actualiza el README raíz

Agrega tu skill a la tabla de catálogo en [README.md](README.md).

### 5. (Si aplica) Añade tests

`tests/test_<skill>.py` con al menos un smoke test. Puedes usar el `pytest`-style sin requerir pytest (los tests existentes corren con `python -m unittest`).

### 6. Pasa el lint local

```bash
# YAML
python skills/yaml-control/yaml_control.py --all

# Markdown
python skills/md-lint-fix/fix-md-lint.py --all --dry-run
```

### 7. Abre el PR

Título conventional: `feat(skill): <nombre> — <one-liner>`. Incluye en el body:

- **Problema** que resuelve.
- **Triggers** principales.
- **Limitaciones** conocidas.

---

---

## 🎨 Estilo

| Lenguaje | Convención |
|---|---|
| **Python** | `ruff` · line-length 120 · type hints donde aporten · `from __future__ import annotations` |
| **Bash** | shellcheck-clean · `set -euo pipefail` salvo justificación |
| **Markdown** | Pasa `md-lint-fix` (eat your own dog food) |
| **YAML** | Pasa `yaml-control` · indentación 2 espacios · sin tabs |

**Sin emojis decorativos en código.** Los warnings y resúmenes pueden usar `✓` / `⚠` / `✗` con moderación.

---

---

## 💎 Tipos de skill que valoramos

- **Productividad** — automatizan trabajo repetitivo (lint, format, scaffolding).
- **Seguridad** — audit, scan, detección de patrones.
- **DevOps** — Docker, Kubernetes, CI/CD helpers.
- **Refactoring** — análisis de calidad de código.

## 🚫 Tipos de skill que NO aceptamos

- Wrappers triviales de una herramienta sin valor añadido (ej. un skill que solo hace `ls`).
- Específicos de un cliente / empresa / proyecto privado.
- Que requieran credenciales hardcoded.
- Sin documentación de qué hace.

---

---

## 🚀 Promoción de skills desde uso personal

Si usas skills locales en `~/.claude/skills/<nombre>/` y crees que uno merece formar parte del toolkit público, sigue el flujo formal documentado en [`docs/skill-promotion.md`](docs/skill-promotion.md):

1. **Validación** — frontmatter, `Path.cwd()`, cross-platform, cero deps.
2. **Copia** al repo bajo `skills/<nombre>/`.
3. **Actualizaciones en cascada** — README, CHANGELOG, ROADMAP, architecture, tests.
4. **Validación local** — `unittest` + `yaml-control` en verde.
5. **Commit + push** — `feat(skills): add <nombre>`.

El agente que mantiene este repo **siempre** pregunta antes de promover. La instalación local es del usuario; el catálogo público es decisión editorial.

---

## 🤗 Código de conducta

Asume buena fe. Sé directo con el código, amable con las personas. Reviews enfocadas en el cambio, no en quien lo escribió.
