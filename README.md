# claude-skills-toolkit

> Skills agentic para [Claude Code](https://claude.com/claude-code) (y compatibles) que automatizan tareas repetitivas de desarrollo: auditoría de seguridad multi-fuente, lint de YAML/Markdown, limpieza de Docker. **Sin dependencias** salvo donde se indica — la mayoría usa solo Python stdlib.

[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Skills](https://img.shields.io/badge/skills-4-1f6feb)](#catálogo)

---

## Qué es un "skill"

Un **skill** es una carpeta con:

- `SKILL.md` — descripción + triggers en frontmatter YAML. Es el contrato que el agente lee para decidir cuándo invocarlo.
- Uno o más scripts (`.py`, `.sh`) que ejecutan la lógica.

Claude Code (y otros runtimes compatibles) cargan los skills desde `~/.claude/skills/<nombre>/` y los invocan cuando el usuario menciona los triggers definidos.

---

## Catálogo

| Skill | Qué hace | Triggers | Dependencias |
|---|---|---|---|
| [**security-audit**](skills/security-audit/) | Audita en **9 capas**: OSV.dev + CISA KEV + EPSS + Bandit SAST + trivy/grype + gitleaks + zizmor + hadolint + typosquat. Genera reporte MD con Plan de Remediación transversal. Modo `--apply --verify` con bumps verificados y revert. | "audita seguridad", "scan CVE", "vulnerability scan" | Solo stdlib (opt-in: `pip install bandit`, `trivy`, `gitleaks`, `zizmor`, `hadolint`) |
| [**yaml-control**](skills/yaml-control/) | Valida YAML en 3 capas: sintaxis + actionlint para workflows GHA + convenciones del repo (actions pinneadas a SHA, permisos explícitos, `fail-fast: false` en matrices grandes). | "valida los yaml", "lint yaml", "actionlint" | `pip install pyyaml` (opt-in: `actionlint`) |
| [**md-lint-fix**](skills/md-lint-fix/) | Detecta y auto-corrige errores de markdownlint (MD024 duplicate headings con contexto del padre, MD040 idioma inferido, MD031/32/34/28/27/22 auto-fix). Trabaja sobre `.md` modificados según `git`. | "arregla el lint MD", "corrige los markdown" | `markdownlint-cli` (npm) |
| [**docker-cleanup**](skills/docker-cleanup/) | Limpia completamente Docker: stops + removes containers, images, volumes, custom networks, build cache. Idempotente. Reporta espacio liberado. | "limpia docker", "wipe docker", "reset docker" | `docker` CLI |

---

## Instalación

### Linux / macOS

```bash
git clone https://github.com/<your-user>/claude-skills-toolkit.git
cd claude-skills-toolkit
./scripts/install.sh
```

### Windows (PowerShell)

```powershell
git clone https://github.com/<your-user>/claude-skills-toolkit.git
cd claude-skills-toolkit
.\scripts\install.ps1
```

El script crea **symlinks** (no copia) desde `~/.claude/skills/<skill>/` hacia este repo. Esto permite que:

1. `git pull` actualiza los skills automáticamente
2. Editas un skill en este repo y el cambio aplica de inmediato
3. Puedes desinstalar con `unlink` sin perder el código

### Instalación manual (sin script)

```bash
cp -r skills/security-audit ~/.claude/skills/
cp -r skills/yaml-control ~/.claude/skills/
# ... etc
```

---

## Uso

Una vez instalados, los skills aparecen disponibles en cualquier sesión de Claude Code. Algunos ejemplos:

```text
> audita la seguridad de este repo
  → invoca security-audit · genera SECURITY_AUDIT_<fecha>.md

> valida los workflows antes de pushear
  → invoca yaml-control · revisa .github/workflows/*.yml

> arregla los markdown modificados
  → invoca md-lint-fix · corrige .md según git status

> limpia docker
  → invoca docker-cleanup · libera espacio
```

También puedes invocarlos directamente como scripts:

```bash
python ~/.claude/skills/security-audit/security_audit.py --layers all --min-severity high
python ~/.claude/skills/yaml-control/yaml_control.py --workflows
bash   ~/.claude/skills/docker-cleanup/scripts/wipe.sh
```

---

## Diseño

### Principios

1. **Cero dependencias por defecto** — los skills funcionan con Python stdlib. Las capas avanzadas son opt-in y degradan silenciosamente si la herramienta no está instalada.
2. **Trabajan desde `Path.cwd()`** — no importa desde qué carpeta los invoques; operan sobre el repo actual.
3. **Honestidad sobre limitaciones** — cada `SKILL.md` documenta qué hace y qué NO hace, incluyendo riesgos conocidos (ej. `security-audit --apply` sin `--verify` puede romper el build).
4. **Cross-platform** — funcionan en Linux, macOS y Windows (Git Bash / MINGW). Solo el shell script `docker-cleanup/wipe.sh` requiere bash.

### Estructura de un skill

```
skills/<nombre>/
├── SKILL.md          ← obligatorio: frontmatter + triggers + uso
├── <script>.py|.sh   ← lógica
└── README.md         ← (opcional) demo extendido / screenshots
```

El frontmatter del `SKILL.md` debe tener:

```yaml
---
name: nombre-del-skill
description: Qué hace + cuándo invocarlo (los triggers van aquí).
              El agente lee este campo para decidir si activarlo.
---
```

---

## Crear un skill nuevo

```bash
cp -r skills/_template skills/mi-skill
# Editar skills/mi-skill/SKILL.md y mi_skill.py
./scripts/install.sh
```

Ver [`CONTRIBUTING.md`](CONTRIBUTING.md) para más detalles.

---

## Roadmap

- [ ] `react-component-scaffold` — genera componente React + tests + stories desde una descripción
- [ ] `sql-migration-safety` — analiza migraciones DB antes de aplicar (lock holding, fk cascades)
- [ ] `dependency-cleanup` — detecta deps no usadas en `requirements.txt` / `package.json`
- [ ] `commit-message-improve` — reescribe commit messages siguiendo conventional commits
- [ ] integración con [Cursor](https://www.cursor.com/) y [Windsurf](https://codeium.com/windsurf)

---

## Licencia

MIT — ver [LICENSE](LICENSE).

---

## Contribuir

PRs bienvenidos. Reglas mínimas:

1. Cada skill debe ser **autónomo** (sin paths absolutos al sistema del autor)
2. `SKILL.md` con frontmatter completo
3. Si requiere binarios externos: documentarlo + degradar gracefully si no está
4. Tests en `tests/` si la lógica es no-trivial
