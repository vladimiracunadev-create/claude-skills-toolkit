# 💼 Para reclutadores / hiring managers

> Lectura de 3 minutos. Qué demuestra este proyecto, qué decisiones técnicas tomé y dónde mirar primero.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Bash](https://img.shields.io/badge/Bash-shell-4EAA25?logo=gnubash&logoColor=white)](https://www.gnu.org/software/bash/)
[![PowerShell](https://img.shields.io/badge/PowerShell-5.1+-5391FE?logo=powershell&logoColor=white)](https://learn.microsoft.com/en-us/powershell/)
[![GitHub Actions](https://img.shields.io/badge/CI-GitHub%20Actions-2088FF?logo=githubactions&logoColor=white)](.github/workflows/ci.yml)

---

## 🎯 TL;DR

`claude-skills-toolkit` es un toolkit de automatización para [Claude Code](https://claude.com/claude-code) — el agente de coding de Anthropic — que empaqueta 4 skills de producción para tareas que cualquier developer hace todos los días: auditar seguridad, lint de YAML, lint de Markdown y limpiar Docker.

**Lenguajes**: Python (1500+ LOC), Bash, PowerShell.
**Stack**: Python stdlib · PyYAML · PowerShell · Bash · GitHub Actions · unittest.
**Sin dependencias innecesarias** — los 4 skills funcionan zero-deps por defecto.

---

---

## 🌟 Qué demuestra este repo

### 1️⃣ Diseño de sistemas — más allá de "hacer que funcione"

[`security-audit`](skills/security-audit/) integra **12 fuentes oficiales** distintas (OSV.dev, CISA KEV, EPSS, Bandit, trivy, grype, gitleaks, zizmor, hadolint, heurística de typosquat) y produce un **Plan de Remediación transversal** priorizado por explotación activa. Modo `--apply --verify` aplica bumps y los revierte si los tests fallan — minimal blast radius.

### 2️⃣ Calidad de software

- **Cross-platform real** — Linux, macOS, Windows (PowerShell + Git Bash). No "funciona en mi máquina".
- **CI cross-matrix** — `.github/workflows/ci.yml` corre tests en ubuntu/windows/macOS × Python 3.11/3.12.
- **Eat your own dog food** — el repo valida sus propios YAML y Markdown con sus propios skills en CI.
- **Tests reales** detectan bugs reales — el primer run de `tests/test_skills_structure.py` encontró 2 bugs de frontmatter en producción.

### 3️⃣ Diseño de API / DX

- **Conversación natural** — el usuario dice "audita la seguridad de este repo" y el agente decide invocar el skill correcto.
- **`Path.cwd()`-centric** — los skills funcionan en cualquier repo sin configuración.
- **Degradación graceful** — si falta una herramienta opcional (`trivy`, `bandit`, etc.), el skill la salta y deja constancia en el reporte.

### 4️⃣ Documentación profesional

Cada skill documenta explícitamente:

- Qué hace.
- Qué **no** hace (limitaciones).
- Qué riesgos tiene (ej. `--apply` sin `--verify` puede romper el build).
- Cuándo invocarlo (triggers en ES + EN).

---

---

## 🧭 Por dónde empezar a leer

| Si te interesa... | Lee |
|---|---|
| Cómo se usa el toolkit | [README.md](README.md) |
| Arquitectura y decisiones de diseño | [docs/architecture.md](docs/architecture.md) |
| El skill más complejo (1500+ LOC) | [skills/security-audit/](skills/security-audit/) — SKILL.md y `security_audit.py` |
| Cómo está organizado el CI | [.github/workflows/ci.yml](.github/workflows/ci.yml) |
| Política de versionado y futuro | [CHANGELOG.md](CHANGELOG.md) · [ROADMAP.md](ROADMAP.md) |

---

---

## 🏗️ Decisiones técnicas que destacan

| Decisión | Por qué |
|---|---|
| **Symlinks en vez de copias** | `git pull` actualiza todos los equipos del usuario sin reinstalar. Fallback automático a copia en Windows sin Developer Mode. |
| **Frontmatter YAML obligatorio en `SKILL.md`** | El agente necesita un contrato declarativo para decidir cuándo invocar el skill. Sin frontmatter, no hay triggers — los tests lo validan. |
| **Cero dependencias por defecto** | Un toolkit que pide instalar 12 paquetes antes de funcionar muere en el `git clone`. Las capas avanzadas son opt-in y degradan. |
| **`subprocess` con argumentos como lista** | Cero shell injection. Cada llamada a `git`, `gh`, `docker` se forma con `["cmd", "arg1", "arg2"]`, nunca strings concatenadas. |
| **Actions pinneadas a SHA en CI** | Defensa contra supply-chain attacks (un `@v4` que cambia bajo tus pies). El propio `yaml-control` lo exige. |

---

---

## 👋 Sobre mí

**Vladimir Acuña** — Full-Stack Developer & Educator.

- Stack: Python · Node.js · Rust · Docker · LangGraph · AWS · Data Science · ML.
- Portfolio: [vladimiracunadev-create.github.io](https://vladimiracunadev-create.github.io)
- GitHub: [@vladimiracunadev-create](https://github.com/vladimiracunadev-create)
- Email: [vladimir.acuna.dev@gmail.com](mailto:vladimir.acuna.dev@gmail.com)

Otros repos que pueden interesarte:

- [**langgraph-realworld**](https://github.com/vladimiracunadev-create/langgraph-realworld) — 25 casos empresariales con LangGraph + FastAPI. 100% backends operativos.
- [**gabysql**](https://github.com/vladimiracunadev-create/gabysql) — Base de datos embebida en Rust, multiplataforma, WAL, API HTTP.
- [**python-data-science-program**](https://github.com/vladimiracunadev-create/python-data-science-program) — 197 clases en 9 partes (Python aplicado, ML, DL, MLOps).
- [**problem-driven-systems-lab**](https://github.com/vladimiracunadev-create/problem-driven-systems-lab) — 12 casos reales Docker-first para diagnóstico de rendimiento y resiliencia.
