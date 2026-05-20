---
name: security-audit
description: Audita la seguridad de cualquier repositorio en 9 capas — dependencias (Python, Node, Go, Java, Rust, Ruby, .NET) vs OSV.dev/NVD/GHSA/PyPA/RustSec; CISA KEV (explotación activa); EPSS (probabilidad de exploit); Bandit SAST sobre el código propio; trivy/grype sobre OS layer del contenedor; gitleaks/detect-secrets en histórico; zizmor para GitHub Actions workflows; hadolint para Dockerfile; typosquat heurístico sobre nombres de paquetes. Genera informe Markdown en el propio repo y opcionalmente aplica correcciones (bump de versiones) con rama git + PR auto-merge. Úsalo cuando el usuario diga "audita seguridad", "busca vulnerabilidades", "scan CVE", "revisa ataques de ciberseguridad", "vulnerability scan", "qué CVEs tiene este repo", "actualiza por seguridad", "SAST", "container scan", "secrets scan" o similar. Trabaja sobre `cwd` por defecto — funciona en cualquier repo. Cada capa es opt-in con `--layers`; las que requieren binarios externos degradan silenciosamente si no están instalados.
---

# security-audit (v2 multi-layer)

Audita CUALQUIER repositorio en **12 capas** complementarias. Produce un informe
Markdown reproducible y, si se indica, aplica correcciones en el mismo repo
dejando trazabilidad en git.

## Capas

| Capa | Fuente | Cubre | Requisito |
|---|---|---|---|
| **osv** | OSV.dev | NVD + GHSA + PyPA + Go vuln DB + RustSec + npm advisories + Maven + RubyGems + NuGet | sólo red |
| **kev** | CISA Known Exploited Vulnerabilities | CVEs con explotación activa documentada (catalogo gov) | sólo red, cache 24h |
| **epss** | FIRST.org EPSS API | Probabilidad de explotación en 30 días (prioriza fixes) | sólo red |
| **recent** | OSV (filtro de fecha) | CVEs publicados en últimos N días (`--recent-days`) | sólo red |
| **news** | CISA Cybersecurity Advisories (RSS) + GitHub Security Advisories recent (gh CLI) | Vendor advisories y CVEs muy recientes con remediation extraída del texto | red + `gh` CLI opcional |
| **pypi-malware** | Sonatype OSS Index | Paquetes retirados / maliciosos / typosquats catalogados | `SONATYPE_OSSI_USER`+`TOKEN` env (free signup) |
| **sast** | Bandit | Vulnerabilidades en TU código Python (eval, hardcoded secrets, SQL concat, etc.) | `pip install bandit` |
| **container** | trivy / grype | OS layer del contenedor (Debian packages que pip no ve) + deps no pinneadas | `trivy` o `grype` binario |
| **secrets** | gitleaks / detect-secrets | Secretos commiteados en histórico git | `gitleaks` o `detect-secrets` |
| **workflows** | zizmor | GitHub Actions: workflow injection, permisos excesivos, unpinned actions | `cargo install zizmor` |
| **dockerfile** | hadolint | Antipatterns en Dockerfile (apt-get upgrade, USER root, etc.) | `hadolint` binario |
| **typosquat** | heurística Levenshtein | Paquetes sospechosos (typo de uno popular: `requets` vs `requests`) | sólo Python |

## Plan de Remediación (transversal)

Cada hallazgo en cualquier capa contribuye con su `fix` (bump, mitigación, workaround,
deshabilitar feature, etc.) extraído del texto del advisory vía heurísticas regex. La
sección final del reporte agrega TODOS los fixes en un checklist priorizado por
(CISA KEV → severidad). Es la **lista accionable única** que el revisor humano marca.

## Modo `--verify` (seguro contra rotura)

Por defecto `--apply` bumpea versiones sin validar. Con `--verify`, por cada bump:

1. Backup del archivo
2. Aplica el bump al manifest
3. Corre `pip install -r requirements.txt`
4. Corre `pytest -x -q` (o `--test-cmd` custom)
5. Si **falla** → **revierte** el bump y registra en sección "Bumps bloqueados"
6. Si **pasa** → mantiene el bump y registra "(verificado: tests OK)"

Bumps se aplican a la **versión mínima que arregla** (minimal blast radius), no a la última disponible. Esto evita saltos de major version innecesarios.

---

## Cuándo invocar este skill

Triggers en español:
- "audita la seguridad del repo / del proyecto"
- "busca vulnerabilidades / CVEs"
- "revisa ataques de ciberseguridad al repo"
- "qué vulnerabilidades tiene `<repo>`"
- "actualiza dependencias por seguridad"
- "scan CVE / security scan"

Triggers en inglés:
- "security audit", "vulnerability scan", "CVE check"
- "audit dependencies", "find vulnerable packages"

Triggers proactivos: si el usuario menciona un CVE específico (ej. "CVE-2024-XXXX")
o un paquete sospechoso (ej. "este uso de python-jose es seguro?"), correr el skill
sobre el repo actual para tener contexto cuantitativo.

---

## Cómo se invoca

Trabaja siempre desde `Path.cwd()` (el repo actual). Sin argumentos = sólo reporte.

```bash
# Sólo reporte (default: layers = osv,kev,epss,typosquat — los que no requieren binarios)
python ~/.claude/skills/security-audit/security_audit.py

# TODAS las capas (las que tengan binario instalado corren, las demás se omiten)
python .../security_audit.py --layers all

# Capas específicas (csv)
python .../security_audit.py --layers osv,sast,container

# Auditar + aplicar fixes (bump de versiones a la primera 'fixed_in' segura)
python .../security_audit.py --apply

# Auditar + aplicar + crear rama git + commit
python .../security_audit.py --apply --git

# Auditar + aplicar + commit + crear PR (requiere gh CLI configurado)
python .../security_audit.py --apply --git --pr

# Sólo ciertos ecosistemas (default: todos los detectados)
python .../security_audit.py --ecosystem PyPI
python .../security_audit.py --ecosystem npm

# Reporte en una carpeta específica
python .../security_audit.py --out-dir docs/security/

# Severidad mínima a incluir en el reporte (low|medium|high|critical)
python .../security_audit.py --min-severity high
```

---

## Qué hace exactamente

### 1) Detección del stack

Escanea `cwd` recursivamente buscando manifests:

| Archivo | Ecosistema OSV | Notas |
|---|---|---|
| `requirements.txt`, `requirements*.txt` | PyPI | Lee pines `pkg==X.Y.Z`. Soporta múltiples (e.g. `cases/*/backend/requirements.txt`) |
| `pyproject.toml` | PyPI | `[project.dependencies]` y `[tool.poetry.dependencies]` |
| `Pipfile.lock`, `poetry.lock` | PyPI | Versiones resueltas |
| `package.json` + `package-lock.json` | npm | Versiones resueltas del lock |
| `yarn.lock` | npm | |
| `go.sum`, `go.mod` | Go | |
| `Cargo.lock` | crates.io | |
| `Gemfile.lock` | RubyGems | |
| `pom.xml` | Maven | Versiones explícitas |
| `*.csproj`, `packages.config` | NuGet | |

Excluye `.git/`, `node_modules/`, `.venv/`, `venv/`, `dist/`, `build/`, `__pycache__/`,
`.claude/worktrees/` (worktrees de Claude antiguos).

### 2) Consulta de fuentes oficiales

- **OSV.dev** (`https://api.osv.dev/v1/querybatch`) — agrega NVD, GHSA,
  PyPA Advisory DB, GHSA, RustSec, Go vuln DB, etc. Sin auth. Batch hasta 1000.
- **CISA KEV** (`https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json`)
  — catálogo de CVEs explotados activamente. Sin auth. Se descarga 1×/sesión y se
  cruza por CVE ID con los hallazgos OSV.
- **GHSA** (opcional, si `gh auth status` ok) — enriquece con metadata extra
  (CVSS vector, descripción detallada).

### 3) Generación de reporte

Escribe `SECURITY_AUDIT_<YYYY-MM-DD>.md` en la raíz del repo (o `--out-dir`),
estructura:

```markdown
# Auditoría de seguridad — <repo> — <fecha>

## Resumen ejecutivo
- Ecosistemas auditados: <list>
- Dependencias revisadas: <N>
- Vulnerabilidades encontradas: <N> (critical: X, high: Y, medium: Z, low: W)
- En CISA KEV (explotación activa): <N>
- Fuentes: OSV.dev, CISA KEV, GHSA

## Hallazgos críticos (explotación activa según CISA KEV)
### CVE-2024-XXXX — <paquete> <vuln_version>
- **Severidad**: CRITICAL (CVSS 9.8) · **CISA KEV** ✓
- **Resumen**: <descripción>
- **Versión afectada**: <range>
- **Fix disponible**: bump a `<fixed_version>`
- **Referencias**: <links OSV/NVD/GHSA>
- **Acción aplicada**: ✅ requirements.txt actualizado (PR #N) / ⚠ no aplicado

## Hallazgos altos
...

## Hallazgos medios / bajos
...

## Acciones aplicadas
- `cases/01-.../requirements.txt`: `pkg==X.Y.Z` → `pkg==X.Y.Z'`
- ...

## Pendientes (sin fix disponible)
- CVE-..., paquete sin versión parchada aún → mitigación recomendada: <texto>

## Cómo reproducir
\```bash
python ~/.claude/skills/security-audit/security_audit.py
\```
```

### 4) Aplicación de fixes (`--apply`)

Para cada hallazgo con `fixed_versions` disponible:
- Si el manifest es `requirements.txt` / `requirements.in` con pin `pkg==X`,
  reemplaza por `pkg==<fixed_version>`.
- Si es `pyproject.toml` / `package.json` con constraint range, ajusta.
- Si es lockfile (`package-lock.json`, `poetry.lock`), recomienda regenerar
  con la herramienta nativa (no se reescribe el lockfile a mano).

Después del bump, intenta correr `pip-compile` para `.in` → `.txt` si está disponible.

### 5) Integración git (`--git`, `--pr`)

- `--git`: crea rama `claude/security-audit-<fecha>`, stagea sólo los manifests
  modificados + el reporte MD, commit con resumen de CVEs corregidos.
- `--pr`: ejecuta `gh pr create` con el título `fix(security): bump N deps
  vulnerables (CVE-...)` y `gh pr merge --squash --auto`.

---

## Limitaciones

- **Falsos positivos**: OSV.dev es agresivo; algunos hallazgos pueden no aplicar
  al uso real del proyecto (e.g. vuln en una función no usada). El reporte
  los lista igualmente — la decisión de bumpear queda en el revisor humano cuando
  no usa `--apply`.
- **Dependencias transitivas**: si el manifest no las pinea, no se auditan
  directamente (la herramienta del ecosistema debe regenerar el lockfile).
- **Sin red**: el skill falla con mensaje claro si OSV.dev no responde.
  CISA KEV se cachea localmente en `~/.cache/security-audit/cisa_kev.json`
  con TTL 24h.

---

## Salida esperada (ejemplo)

```
Security audit — repo: C:/dev/langgraph-realworld
  Detectados: 26 manifests PyPI, 0 npm, 0 otros
  Consultando OSV.dev (batch 26 grupos)... OK
  Descargando CISA KEV catalog... OK (cached, 1342 CVEs vivos)
  Cruzando con GHSA... OK

Resultados:
  - 3 vulnerabilidades encontradas
    - 1 critical (CVE-2026-XXXXX en pkg-foo 1.2.3 → fix en 1.2.5) [CISA KEV ✓]
    - 2 high (CVE-..., CVE-...)
  - 0 medium / low

Reporte escrito en: SECURITY_AUDIT_2026-05-19.md

Aplicado --apply:
  - cases/01-.../requirements.txt: pkg-foo==1.2.3 → pkg-foo==1.2.5
  - cases/02-.../requirements.txt: ...

git: rama claude/security-audit-2026-05-19 creada, 2 archivos staged.
PR creado: #69 (auto-merge habilitado).
```

---

## Integración con flujo de trabajo

- **Pre-release**: correr antes de publicar release (`--apply --git --pr`).
- **CRON**: agregar al ROADMAP "ejecutar security-audit semanal".
- **Combinable con [[yaml-control]]**: el agente puede invocar ambos seguidos
  antes de pushear un release que toque deps + workflows.
