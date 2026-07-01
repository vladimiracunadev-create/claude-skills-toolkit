<div align="center">

# 🧰 claude-skills-toolkit

### ⚡ Skills agentic listos para producción para [Claude Code](https://claude.com/claude-code) y runtimes compatibles

Automatización de tareas repetitivas de desarrollo — 🔒 auditoría de seguridad multi-fuente, 📋 lint de YAML, 📝 lint de Markdown, 🐳 limpieza de Docker, 🩺 diagnóstico de `compose.yml`, 🪝 guardián pre-commit, 🛡️ guardián pre-push, 📸 screenshots web y 🐍 coherencia de versión de Python.
**Sin dependencias innecesarias** — la mayoría usa solo Python stdlib.

[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/vladimiracunadev-create/claude-skills-toolkit?logo=github&color=8957e5)](https://github.com/vladimiracunadev-create/claude-skills-toolkit/releases)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Skills](https://img.shields.io/badge/skills-9-1f6feb)](#-catálogo)
[![Platforms](https://img.shields.io/badge/platforms-linux%20%7C%20macOS%20%7C%20windows-555?logo=linux&logoColor=white)](#-instalación)
[![CI](https://github.com/vladimiracunadev-create/claude-skills-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/vladimiracunadev-create/claude-skills-toolkit/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-8%20passing-brightgreen?logo=pytest&logoColor=white)](tests/)
[![Supply chain hardened](https://img.shields.io/badge/supply%20chain-hardened-2da44e?logo=shieldsdotio&logoColor=white)](docs/supply-chain-security.md)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?logo=github)](CONTRIBUTING.md)
[![Made with ❤ in Chile](https://img.shields.io/badge/made_in-Chile-d52b1e)](https://github.com/vladimiracunadev-create)

[**📦 Instalación**](#-instalación) · [**🗂️ Catálogo**](#-catálogo) · [**🚀 Uso**](#-uso) · [**🧭 Diseño**](#-diseño) · [**📚 Documentación**](#-documentación) · [**🤝 Contribuir**](CONTRIBUTING.md)

</div>

---

## 💡 ¿Qué es un "skill"?

Un **skill** es una carpeta autocontenida que el agente carga al iniciar la sesión:

```text
skills/<nombre>/
├── SKILL.md          # Contrato · frontmatter YAML + descripción + triggers
├── <script>.py|.sh   # Lógica ejecutable
└── README.md         # (opcional) demo extendido
```

El agente lee el `description` del frontmatter para decidir **cuándo** invocarlo automáticamente. El script vive en `~/.claude/skills/<nombre>/` (instalado vía symlink) y se ejecuta sobre `Path.cwd()` — el repo donde estás trabajando ahora.

```mermaid
flowchart LR
    A[👤 Usuario habla] --> B{🧠 Modelo<br/>matchea triggers}
    B -->|invoca| C[⚙️ Skill script]
    C -->|Path.cwd| D[📁 Repo del usuario]
    D --> E[📝 Reporte / cambios]
    style A fill:#1f6feb,color:#fff
    style B fill:#8957e5,color:#fff
    style C fill:#2da44e,color:#fff
    style D fill:#bf8700,color:#fff
    style E fill:#cf222e,color:#fff
```

---

## 🗂️ Catálogo

<table>
<thead>
<tr>
<th width="22%">Skill</th>
<th width="48%">Qué hace</th>
<th width="20%">Triggers</th>
<th width="10%">Deps</th>
</tr>
</thead>
<tbody>
<tr>
<td>

### 🔒 [security-audit](skills/security-audit/)

<sub>1565 LOC · Python · ![status](https://img.shields.io/badge/stable-green)</sub>

</td>
<td>

Auditoría en **12 capas**: OSV.dev · CISA KEV · EPSS · Bandit SAST · trivy/grype · gitleaks · zizmor · hadolint · typosquat heurístico.
Genera reporte Markdown con **Plan de Remediación transversal**. Modo `--apply --verify` aplica bumps y los revierte si los tests fallan.

</td>
<td>

🔎 `audita seguridad`<br>
🛡️ `scan CVE`<br>
🚨 `vulnerability scan`

</td>
<td>

stdlib<br>
<sub>(opt-in: bandit, trivy, gitleaks, zizmor, hadolint)</sub>

</td>
</tr>
<tr>
<td>

### 📋 [yaml-control](skills/yaml-control/)

<sub>271 LOC · Python · ![status](https://img.shields.io/badge/stable-green)</sub>

</td>
<td>

Validación YAML en 3 capas: sintaxis + `actionlint` para workflows + convenciones del repo (actions pinneadas a SHA, permisos explícitos, `fail-fast: false` en matrices).

</td>
<td>

✅ `valida los yaml`<br>
🔧 `lint yaml`<br>
⚙️ `actionlint`

</td>
<td>

`pyyaml`<br>
<sub>(opt-in: actionlint)</sub>

</td>
</tr>
<tr>
<td>

### 📝 [md-lint-fix](skills/md-lint-fix/)

<sub>359 LOC · Python · ![status](https://img.shields.io/badge/stable-green)</sub>

</td>
<td>

Detecta y auto-corrige `markdownlint-cli2`: MD024 con contexto del padre, MD040 infiriendo idioma, MD031/32/34/28/27/22 vía `--fix`. Trabaja sobre `.md` modificados según `git`.

</td>
<td>

✨ `arregla el lint MD`<br>
📄 `corrige los markdown`

</td>
<td>

`markdownlint-cli2`<br>
<sub>(pnpm)</sub>

</td>
</tr>
<tr>
<td>

### 🐳 [docker-cleanup](skills/docker-cleanup/)

<sub>67 LOC · Bash · ![status](https://img.shields.io/badge/stable-green)</sub>

</td>
<td>

Wipe completo de Docker: containers + images + volumes + custom networks + build cache. Idempotente. Reporta espacio liberado con `docker system df` antes/después.

</td>
<td>

🧹 `limpia docker`<br>
💥 `wipe docker`<br>
♻️ `reset docker`

</td>
<td>

`docker` CLI

</td>
</tr>
<tr>
<td>

### 🩺 [docker-compose-doctor](skills/docker-compose-doctor/)

<sub>400 LOC · Python · ![status](https://img.shields.io/badge/stable-green)</sub>

</td>
<td>

Análisis estático de `compose.yml`: puertos host duplicados, healthchecks faltantes, `depends_on` sin `condition: service_healthy`, imágenes con `:latest`, volúmenes huérfanos, `env_file` inexistentes. Detecta lo que el schema oficial no captura.

</td>
<td>

🩺 `revisa el compose`<br>
🧰 `docker compose lint`<br>
🚦 `por qué no levanta`

</td>
<td>

`pyyaml`

</td>
</tr>
<tr>
<td>

### 🪝 [pre-commit-guard](skills/pre-commit-guard/)

<sub>~260 LOC · Python · ![status](https://img.shields.io/badge/stable-green)</sub>

</td>
<td>

Gemelo rápido de `pre-push-guard` pero sobre lo **staged**: corre `yaml-control` + `md-lint-fix --dry-run` sobre `git diff --cached` antes de cada commit. Bloquea que un YAML roto o un Markdown malformado entre al historial local. No corre pytest — mantiene el commit < 2s.

</td>
<td>

🪝 `pre-commit`<br>
✅ `valida antes de commitear`<br>
🚦 `guard antes de commit`

</td>
<td>

stdlib

</td>
</tr>
<tr>
<td>

### 🛡️ [pre-push-guard](skills/pre-push-guard/)

<sub>322 LOC · Python · ![status](https://img.shields.io/badge/stable-green)</sub>

</td>
<td>

Orquestador pre-push: corre `yaml-control` + `md-lint-fix --dry-run` + `pytest` sobre el diff vs `origin/<branch>`. Fail-fast con reporte unificado. Opt-in como git hook con `--install-hook`.

</td>
<td>

🛡️ `valida antes de pushear`<br>
✅ `corre todos los checks`<br>
🪝 `pre-push hook`

</td>
<td>

stdlib<br>
<sub>(opt-in: pytest)</sub>

</td>
</tr>
<tr>
<td>

### 📸 [web-snap](skills/web-snap/)

<sub>213 LOC · Python · ![status](https://img.shields.io/badge/stable-green) · ![platform](https://img.shields.io/badge/windows-only-0078D6)</sub>

</td>
<td>

Screenshots de URLs web en **Windows** usando Chrome/Edge ya instalado. Sin Selenium ni Playwright. Trae al frente la ventana vía `user32.SetWindowPos(HWND_TOPMOST)` antes de capturar. Modo single o batch desde JSON.

</td>
<td>

📸 `captura pantalla`<br>
🌐 `screenshot de esta URL`<br>
📋 `evidencia visual de despliegue`

</td>
<td>

`pillow`

</td>
</tr>
<tr>
<td>

### 🐍 [python-version-control](skills/python-version-control/)

<sub>~540 LOC · Python · ![status](https://img.shields.io/badge/stable-green)</sub>

</td>
<td>

Audita la coherencia de versión de Python entre 12+ fuentes de verdad: `pyproject.toml` (`requires-python`, classifiers, `target-version` de ruff/mypy/black), `Dockerfile FROM`, `.github/workflows/*.yml` (`setup-python`), `.python-version`, `runtime.txt`, `tox.ini`, `noxfile.py`, `pre-commit`. Detecta drift y propone versión canónica. `--fix` es opt-in con confirmación.

</td>
<td>

🐍 `audita versión python`<br>
🔀 `drift python`<br>
📌 `python version control`

</td>
<td>

stdlib<br>
<sub>(opt-in: `tomli` para Python < 3.11)</sub>

</td>
</tr>
</tbody>
</table>

---

## 📦 Instalación

> **Prerequisitos:** 🐍 Python 3.11+ · 🌿 Git · 🤖 (opcional) [Claude Code](https://claude.com/claude-code).

### ⚡ Instalación en una máquina nueva (one-liner)

**🐧 Linux · 🍎 macOS · Git Bash:**

```bash
git clone https://github.com/vladimiracunadev-create/claude-skills-toolkit.git ~/claude-skills-toolkit \
  && cd ~/claude-skills-toolkit \
  && ./scripts/install.sh
```

**🪟 Windows · PowerShell:**

```powershell
git clone https://github.com/vladimiracunadev-create/claude-skills-toolkit.git $env:USERPROFILE\claude-skills-toolkit; `
  cd $env:USERPROFILE\claude-skills-toolkit; `
  .\scripts\install.ps1
```

> 💡 **Windows.** Para que los symlinks funcionen activa **Developer Mode** (*Settings → Privacy & security → For developers*) o ejecuta PowerShell como administrador. Si no, `install.ps1` cae a copia automáticamente.

### 🔄 Actualizar en cualquier equipo

```bash
cd ~/claude-skills-toolkit && git pull
```

Como la instalación usa symlinks, `git pull` propaga los cambios en caliente — sin reinstalar.

### 🔍 Qué hace el instalador

```mermaid
flowchart TD
    A[git clone] --> B[./scripts/install.sh]
    B --> C{Para cada skill}
    C --> D[¿Existe symlink<br/>previo?]
    D -->|sí| E[🗑️ rm symlink]
    D -->|no| F
    E --> F[🔗 ln -s repo → ~/.claude/skills]
    F --> G[✅ Claude Code lo<br/>descubre al iniciar]
    style A fill:#1f6feb,color:#fff
    style G fill:#2da44e,color:#fff
```

Es idempotente. Ventajas frente a copiar:

- 🚀 `git pull` basta para actualizar todos los equipos.
- 🔥 Editar un skill en el repo aplica en caliente.
- 🧹 Desinstalar = borrar el symlink (el repo queda intacto).

Detalles completos —incluyendo troubleshooting, instalación paso a paso y sincronización de varios equipos— en [INSTALL.md](INSTALL.md).

---

## 🚀 Uso

Una vez instalados, los skills se invocan **conversacionalmente** desde Claude Code:

```text
> audita la seguridad de este repo
  → 🔒 invoca security-audit · genera SECURITY_AUDIT_<fecha>.md

> valida los workflows antes de pushear
  → 📋 invoca yaml-control · revisa .github/workflows/*.yml

> arregla los markdown modificados
  → 📝 invoca md-lint-fix · corrige .md según git status

> limpia docker
  → 🐳 invoca docker-cleanup · libera espacio
```

También como scripts directos:

```bash
python ~/.claude/skills/security-audit/security_audit.py --layers all --min-severity high
python ~/.claude/skills/yaml-control/yaml_control.py --workflows
bash   ~/.claude/skills/docker-cleanup/scripts/wipe.sh
```

---

## 🧭 Diseño

### 🎯 Principios

| | |
|---|---|
| 🪶 **Zero-deps por defecto** | Funcionan con Python stdlib. Las capas avanzadas son opt-in y degradan silenciosamente si la herramienta no está disponible. |
| 📁 **`Path.cwd()`-centric** | No importa desde qué carpeta se invoquen — operan sobre el repo actual. |
| 🔍 **Honestidad sobre límites** | Cada `SKILL.md` documenta qué hace, qué **no** hace, y los riesgos (ej. `--apply` sin `--verify` puede romper el build). |
| 🌐 **Cross-platform** | Linux, macOS, Windows (Git Bash / MINGW / PowerShell). Solo `docker-cleanup` requiere bash. |
| 🐕 **Eat your own dog food** | El propio repo se valida con `yaml-control` + `md-lint-fix` en [CI](.github/workflows/ci.yml). |
| 🛡️ **Supply chain hardened** | Cualquier dependencia Node usa `pnpm v11` (postinstall bloqueado + cuarentena de 24 h por defecto). Actions pinneadas a SHA. Ver [docs/supply-chain-security.md](docs/supply-chain-security.md). |

### 🧬 Anatomía de un skill

```text
skills/<nombre>/
├── SKILL.md          ← obligatorio · frontmatter + triggers + uso
├── <script>.py|.sh   ← lógica
└── README.md         ← opcional · screenshots, demos
```

El frontmatter mínimo:

```yaml
---
name: nombre-del-skill
description: Qué hace + cuándo invocarlo (triggers en español e inglés).
             El agente lee este campo para decidir si activarlo.
---
```

---

## 🆕 Crear un skill nuevo

```bash
cp -r skills/_template skills/mi-skill
# Editar skills/mi-skill/SKILL.md y main.py
./scripts/install.sh
```

Ver [CONTRIBUTING.md](CONTRIBUTING.md) para las reglas completas.

---

## 📚 Documentación

| Documento | Para qué |
|---|---|
| 📘 [README.md](README.md) | Entry point · catálogo + quick start *(estás aquí)* |
| 📦 [INSTALL.md](INSTALL.md) | Instalación, actualización y sincronización entre equipos |
| 🤝 [CONTRIBUTING.md](CONTRIBUTING.md) | Cómo añadir un skill nuevo + estilo de código |
| 📋 [CHANGELOG.md](CHANGELOG.md) | Historial de versiones (Keep a Changelog + SemVer) |
| 🗺️ [ROADMAP.md](ROADMAP.md) | Próximos hitos y no-objetivos explícitos |
| 🔐 [SECURITY.md](SECURITY.md) | Política de seguridad y cómo reportar vulnerabilidades |
| 🛡️ [docs/supply-chain-security.md](docs/supply-chain-security.md) | Política frente a ataques Shai-Hulud · por qué `pnpm` en vez de `npm` |
| 🆘 [SUPPORT.md](SUPPORT.md) | Canales por tipo de problema · cómo pedir ayuda |
| 🤗 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | Código de conducta de la comunidad |
| 🏗️ [docs/architecture.md](docs/architecture.md) | Arquitectura interna · decisiones de diseño |
| 🚀 [docs/skill-promotion.md](docs/skill-promotion.md) | Flujo formal para promover skills locales al toolkit |
| 💼 [RECRUITER.md](RECRUITER.md) | Para reclutadores · qué demuestra este proyecto |

---

## 🗺️ Roadmap

Resumen — versión completa en [ROADMAP.md](ROADMAP.md).

**v0.2.0 · ✅ publicada 2026-07-01** — 🐍 `python-version-control` + workflow de release automatizado.

**v0.3.0 · en curso:**

- [x] 🪝 `pre-commit-guard` — gemelo rápido de `pre-push-guard` sobre lo staged *(primer hito v0.3.0)*
- [ ] 🧹 `dependency-cleanup` — detecta dependencias sin uso en `requirements.txt` / `package.json`
- [ ] ✍️ `commit-message-improve` — reescribe commits siguiendo conventional commits
- [ ] 🗃️ `sql-migration-safety` — analiza migraciones DB (lock holding, FK cascades)
- [ ] ⚛️ `react-component-scaffold` — genera componente React + tests + stories
- [ ] 🧪 Tests por skill (happy path por cada uno)
- [ ] 🔌 Integración explícita con [Cursor](https://www.cursor.com/) y [Windsurf](https://codeium.com/windsurf)

¿Sugerencias? 💬 Abre un [issue](https://github.com/vladimiracunadev-create/claude-skills-toolkit/issues).

---

## 🤝 Contribuir

PRs bienvenidos. Antes de abrir uno, revisa [CONTRIBUTING.md](CONTRIBUTING.md). Reglas mínimas:

1. 🎒 Cada skill debe ser **autónomo** (sin paths absolutos al sistema del autor).
2. 📜 `SKILL.md` con frontmatter completo (`name` + `description` con triggers).
3. 🪶 Cero dependencias por defecto. Si requiere binarios externos: documentarlo y degradar gracefully.
4. 🧪 Tests en `tests/` si la lógica es no-trivial.

---

## 📄 Licencia

[MIT](LICENSE) © 2026 [Vladimir Acuña](https://github.com/vladimiracunadev-create)

<div align="center">

### 🌟 Otros proyectos del autor

[🤖 langgraph-realworld](https://github.com/vladimiracunadev-create/langgraph-realworld) ·
[🗄️ gabysql](https://github.com/vladimiracunadev-create/gabysql) ·
[🧪 problem-driven-systems-lab](https://github.com/vladimiracunadev-create/problem-driven-systems-lab) ·
[📚 python-data-science-program](https://github.com/vladimiracunadev-create/python-data-science-program) ·
[🐳 docker-labs](https://github.com/vladimiracunadev-create/docker-labs)

---

<sub>Hecho con ☕ y demasiados PRs revisados a la 1 a.m.</sub>

</div>
