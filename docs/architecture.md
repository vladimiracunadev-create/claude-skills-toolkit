# 🏗️ Arquitectura

> Cómo está organizado `claude-skills-toolkit` por dentro, y por qué.

---

## 🌳 Vista en árbol

```text
claude-skills-toolkit/
├── 📘 README.md              ← entry point · catálogo + quick start
├── 📦 INSTALL.md             ← instalación / desinstalación / troubleshooting
├── 🤝 CONTRIBUTING.md        ← reglas para PRs
├── 📋 CHANGELOG.md           ← historial de versiones (Keep a Changelog)
├── 🗺️ ROADMAP.md             ← próximos hitos + no-objetivos
├── 🔐 SECURITY.md            ← política de seguridad
├── 🆘 SUPPORT.md             ← canales por tipo de problema
├── 🤗 CODE_OF_CONDUCT.md     ← Contributor Covenant 2.1
├── 💼 RECRUITER.md           ← qué demuestra este proyecto
├── 📄 LICENSE                ← MIT
│
├── 🛠️ scripts/
│   ├── install.sh         ← Linux/macOS/Git-Bash · symlinks idempotentes
│   ├── install.ps1        ← Windows PowerShell · symlink con fallback a copia
│   ├── uninstall.sh       ← solo remueve symlinks que apunten al repo
│   └── uninstall.ps1      ← idem, versión PowerShell
│
├── 🗂️ skills/                     (cada skill: SKILL.md + README.md + script)
│   ├── _template/         ← copia para crear skills nuevos
│   ├── 🔒 security-audit/         ← 12 capas · OSV/KEV/EPSS/SAST/... + cobertura real del scan
│   ├── 📋 yaml-control/           ← yaml + actionlint + convenciones repo
│   ├── 📝 md-lint-fix/            ← wrapper inteligente de markdownlint-cli2
│   ├── 🐳 docker-cleanup/         ← wipe completo de Docker (bash)
│   ├── 🩺 docker-compose-doctor/  ← análisis estático de compose.yml
│   ├── 🪝 pre-commit-guard/       ← orquestador pre-commit (yaml + md sobre staged, sin pytest)
│   ├── 🛡️ pre-push-guard/         ← orquestador pre-push (yaml + md + pytest)
│   ├── 📸 web-snap/               ← screenshots de URLs en Windows (Chrome/Edge + Pillow)
│   ├── 🐍 python-version-control/ ← audita drift de versión Python (12+ fuentes)
│   └── 🧭 repo-coherence-audit/   ← reconcilia docs↔repo (versión/tests/workflows/pins)
│
├── 🧪 tests/                 ← unittest, sin dependencias extras
│   ├── test_skills_structure.py        ← estructura: frontmatter + README + scripts
│   └── test_security_audit_coverage.py ← funcionales: compute_coverage happy paths
│
├── 📚 docs/
│   ├── architecture.md            ← este archivo
│   ├── skill-promotion.md         ← flujo local → toolkit
│   └── supply-chain-security.md   ← política npm/pnpm · Shai-Hulud
│
└── ⚙️ .github/
    └── workflows/
        ├── ci.yml         ← yaml-control + md-lint + tests cross-platform
        └── release.yml    ← tag v* → zip por skill + bundle + GitHub Release
```

---

## 🧠 Modelo mental

Un **skill** = un contrato + un ejecutable + docs humanas. El contrato vive en `SKILL.md` (frontmatter YAML con `name` + `description` + triggers — lo lee el agente); el ejecutable es Python o Bash; el `README.md` documenta para humanos (diagramas, casos de uso, limitaciones).

El runtime (Claude Code) carga todos los directorios bajo `~/.claude/skills/`. Cuando el usuario habla, el modelo compara la intención con cada `description` y decide invocar el skill apropiado.

### Flujo de invocación

```mermaid
sequenceDiagram
    actor U as 👤 Usuario
    participant M as 🧠 Modelo (Claude)
    participant S as ⚙️ Skill script
    participant R as 📁 Repo (Path.cwd)

    U->>M: "audita la seguridad del repo"
    M->>M: Matchea triggers en<br/>SKILL.md descriptions
    M->>S: subprocess(security_audit.py)
    S->>R: walk_repo() · find manifests
    S->>S: Consulta OSV.dev, CISA KEV, EPSS
    S->>R: Escribe SECURITY_AUDIT_2026-05-19.md
    S-->>M: stdout · resumen
    M-->>U: 📊 "3 vulns encontradas, 1 crítica..."
```

### Topología de archivos

```mermaid
flowchart LR
    subgraph repo["📁 claude-skills-toolkit (clone)"]
        skill1["🔒 skills/security-audit/"]
        skill2["📋 skills/yaml-control/"]
        skill3["📝 skills/md-lint-fix/"]
        skill4["🐳 skills/docker-cleanup/"]
    end

    subgraph home["🏠 ~/.claude/skills/ (symlinks)"]
        link1["🔗 security-audit"]
        link2["🔗 yaml-control"]
        link3["🔗 md-lint-fix"]
        link4["🔗 docker-cleanup"]
    end

    subgraph runtime["🤖 Claude Code runtime"]
        loader["Skill loader"]
    end

    skill1 -.->|ln -s| link1
    skill2 -.->|ln -s| link2
    skill3 -.->|ln -s| link3
    skill4 -.->|ln -s| link4

    link1 --> loader
    link2 --> loader
    link3 --> loader
    link4 --> loader

    style repo fill:#1f6feb,color:#fff
    style home fill:#bf8700,color:#fff
    style runtime fill:#2da44e,color:#fff
```

---

## 🎯 Decisiones de diseño

### 1️⃣ `Path.cwd()` en vez de paths embebidos

Los skills nunca asumen una ruta absoluta del autor. Todo lo relativo se calcula desde el directorio de trabajo actual. Esto permite que el mismo skill instalado una vez funcione en cualquier repositorio.

### 2️⃣ Symlinks en vez de copias

`install.sh` y `install.ps1` crean symlinks desde `~/.claude/skills/` hacia este repo.

| | Symlink | Copia |
|---|:-:|:-:|
| ✅ `git pull` actualiza | sí | requiere reinstalar |
| 🔥 Edición en caliente | sí | no |
| 🧹 Desinstalar limpio | sí | sí |
| 🪟 Funciona en Windows sin Dev Mode | no | sí (fallback) |

### 3️⃣ Cero dependencias por defecto

Los 10 skills funcionan con Python stdlib + herramientas estándar del SO (git, docker) — las excepciones (`pyyaml`, `pillow`, `markdownlint-cli2`) están documentadas por skill en [INSTALL.md](../INSTALL.md). Las capas avanzadas (Bandit, trivy, gitleaks, etc.) son **opt-in** y degradan silenciosamente si no están instaladas. El reporte deja constancia de qué capa se saltó y por qué.

### 4️⃣ Honestidad sobre limitaciones

Cada `SKILL.md` tiene una sección explícita **"Qué NO hace / limitaciones"**. Un skill que esconde sus límites genera bugs sutiles cuando el agente lo invoca en un contexto inadecuado.

### 5️⃣ Eat your own dog food

El propio repo se valida en CI con `yaml-control` y `markdownlint-cli2`. Si los skills no son suficientemente buenos para validar a su propio toolkit, no son suficientemente buenos para nadie.

---

## 🔄 Flujo de instalación

```mermaid
flowchart TD
    A[🌿 git clone] --> B{./scripts/install.sh}
    B --> C[Itera skills/]
    C --> D{¿Existe<br/>~/.claude/skills/X?}
    D -->|sí| E[🗑️ rm previo]
    D -->|no| F[🔗 ln -s]
    E --> F
    F --> G{¿Más skills?}
    G -->|sí| C
    G -->|no| H[✅ Listo]
    H --> I[🤖 Claude Code los<br/>descubre en próxima sesión]

    style A fill:#1f6feb,color:#fff
    style H fill:#2da44e,color:#fff
    style I fill:#8957e5,color:#fff
```

Idempotente: re-ejecutarlo reemplaza los symlinks viejos sin romper nada.

---

## ➕ Cómo añadir un skill nuevo

Ver [CONTRIBUTING.md](../CONTRIBUTING.md) para el workflow detallado. Resumen:

```mermaid
flowchart LR
    A[1.cp _template] --> B[2.Editar SKILL.md]
    B --> C[3.Implementar script]
    C --> D[4.Update README]
    D --> E[5.Add tests/]
    E --> F[6.PR]
    style A fill:#1f6feb,color:#fff
    style F fill:#2da44e,color:#fff
```

---

## ✅ Estado del CI

El workflow [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) corre en cada push y PR a `main`:

| Job | Qué hace | Plataforma |
|---|---|---|
| 📋 `yaml-lint` | Ejecuta `yaml-control --all` + `actionlint` sobre el propio repo | 🐧 ubuntu-latest |
| 📝 `markdown-lint` | `markdownlint-cli2` sobre todos los `.md` (report-only) | 🐧 ubuntu-latest |
| 🧪 `python-tests` | `python -m unittest discover -s tests` (17 tests) | 🐧🍎🪟 ubuntu / macOS / windows · Python 3.11 + 3.12 |

## 🚀 Release automation

El workflow [`.github/workflows/release.yml`](../.github/workflows/release.yml) se dispara al pushear un tag `v*`:

1. Empaqueta **cada skill como zip individual** (`<skill>-vX.Y.Z.zip`).
2. Empaqueta el **bundle completo** del toolkit (skills + scripts + docs).
3. Extrae las release notes de la sección correspondiente del `CHANGELOG.md`.
4. Crea el GitHub Release con todos los assets (o actualiza los assets si ya existe).

Flujo de release: mover `[Unreleased]` → `[X.Y.Z]` en CHANGELOG → commit → `git tag -a vX.Y.Z` → `git push origin vX.Y.Z`. Todo lo demás es automático.

### Matriz de tests

```mermaid
flowchart TD
    A[🌿 push a main / PR] --> B[3 jobs en paralelo]
    B --> C[📋 yaml-lint]
    B --> D[📝 markdown-lint]
    B --> E[🧪 python-tests]

    E --> E1[🐧 ubuntu / 3.11]
    E --> E2[🐧 ubuntu / 3.12]
    E --> E3[🍎 macOS / 3.11]
    E --> E4[🍎 macOS / 3.12]
    E --> E5[🪟 windows / 3.11]
    E --> E6[🪟 windows / 3.12]

    style A fill:#1f6feb,color:#fff
    style B fill:#8957e5,color:#fff
```
