# 📋 Changelog

Todos los cambios notables de `claude-skills-toolkit` se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el versionado [SemVer](https://semver.org/lang/es/).

[![Keep a Changelog](https://img.shields.io/badge/changelog-Keep_a_Changelog-E05735?logo=keepachangelog)](https://keepachangelog.com)
[![SemVer](https://img.shields.io/badge/versioning-SemVer-3F4551)](https://semver.org)

---

## 🚧 [Unreleased]

### ✨ Añadido

- **`security-audit`: reporte de cobertura real del scan.** Nueva función `compute_coverage()` que compara lo *declarado* en cada manifest contra lo que los parsers *realmente escanearon*, y hace el gap explícito en tres lugares: (1) warning en consola (`⚠ Cobertura: N deps FUERA del scan`), (2) línea de % de cobertura en el resumen ejecutivo del reporte, (3) sección "🔍 Cobertura del scan de dependencias" con tabla `dep | spec | archivo:línea | motivo`. Detecta: deps PyPI sin pin exacto (`flask>=2.0`, `pandas`), editable installs y URLs en `requirements*.txt`, deps de `pyproject.toml` (PEP 621 + Poetry, parseadas con `tomllib`) no capturadas por el scanner, `package.json` sin `package-lock.json`, `go.mod` sin `go.sum`, `Cargo.toml` sin `Cargo.lock`. Caso extremo endurecido: si NINGUNA dep es escaneable pero hay declaradas, ahora sale exit 1 con aviso claro (antes: exit 0 con "No se detectaron manifests", engañoso). Motivación: un reporte "0 vulnerabilidades" con 2 de 3 deps sin escanear daba falsa sensación de seguridad — ahora el reporte confiesa "0 vulnerabilidades en el 33% que pude revisar". Cambio 100% aditivo: `coverage` es kwarg opcional de `build_report()`, el scan y los exit codes existentes no cambian. Incluye `tests/test_security_audit_coverage.py` (8 tests happy-path — primer test funcional por skill, adelanta el item de v0.3.0).

- **`README.md` profesional en cada skill** (9 archivos, uno por skill de producción). Cada uno cubre: qué hace (con diagrama Mermaid), triggers de activación, instalación (vía toolkit installer o standalone desde release), uso con tabla de flags, casos de uso reales con outputs esperados, cómo funciona por dentro, dependencias, limitaciones y skills relacionados. Enlazados desde el catálogo del README principal (`skills/<name>/README.md` en lugar de `skills/<name>/`). Test estructural nuevo `test_each_skill_has_readme_md` que verifica presencia, longitud mínima y secciones obligatorias. Sección "Anatomía de un skill" del README principal actualizada para reflejar que README.md ahora es obligatorio junto con SKILL.md (dos archivos, dos audiencias: contrato-agente vs docs-humanos).
- `skills/pre-commit-guard/` — nuevo skill: gemelo rápido de `pre-push-guard` sobre archivos **staged**. Corre `yaml-control` + `md-lint-fix --dry-run` sobre `git diff --cached --name-only --diff-filter=ACMR` antes de cada `git commit`, con reporte unificado y fail-fast. Objetivo de tiempo < 2s — no corre pytest (los tests pesados quedan para `pre-push-guard`). Soporta `--install-hook` / `--uninstall-hook` para registrarse como git `pre-commit` hook (opt-in, backup automático de hook previo como `.pre-commit.bak`). Cierra el item `pre-commit hook configurable` del ROADMAP v0.3.0. **Justificación:** hasta ahora un YAML roto o Markdown malformado entraba al historial local y forzaba `git commit --amend`/rebase; con este skill el commit se aborta antes. Complementa a `pre-push-guard` sin solaparse (dos capas de defensa: rápida por commit / completa por push). Triggers: "valida antes de commitear", "pre-commit", "guard antes de commit", "instala pre-commit hook".
- `skills/_template/README.md` — esqueleto nuevo con las secciones obligatorias (🎯/📦/🚀), para que cada skill nuevo parta con la estructura que exigen los tests.

### 🐛 Corregido

- `security-audit`: las capas repo-level (`sast`, `secrets`, `workflows`, `dockerfile`, `container`) ahora corren aunque el repo no declare dependencias. Antes, un repo sin manifests hacía return temprano con "No se detectaron manifests" y se saltaba TODAS las capas — incluso las que auditan el repo en sí (Bandit sobre el código propio, gitleaks sobre el histórico, zizmor sobre workflows). Detectado al auditar el propio toolkit (cero deps por diseño): el fix habilitó a Bandit encontrar 54 hallazgos SAST reales que antes eran invisibles. Además `skills/` y `lib/` se añaden a los directorios candidatos de Bandit (antes solo `src/cases/shared/scripts/app/backend`).
- `security-audit`: crash (`ValueError` en `Path.relative_to`) al usar `--out-dir` apuntando fuera del repo auditado. El reporte se escribía bien pero el print final del path fallaba. Detectado en demo real con reporte dirigido a un directorio temporal. Ahora si el path no es relativo al repo se muestra absoluto.
- `security-audit`: la sección "Cómo reproducir" del reporte generado embebía un path absoluto del autor (`C:/Users/vbav/...`) — cada reporte de cualquier usuario incluía esa ruta ajena. Ahora usa `~/.claude/skills/...`. Además, los ejemplos de salida en la documentación de `security-audit`, `yaml-control` y `docker-compose-doctor` usaban nombres de repos personales del autor — sustituidos por `/ruta/a/mi-proyecto`.

### 🔄 Cambiado

- **Barrido documental completo** — toda la documentación alineada con el estado real del toolkit (9 skills, 17 tests, release v0.2.0 publicado):
  - `INSTALL.md`: "los 4 skills" → 9; tabla de dependencias ampliada a los 9 skills; `git checkout v0.2.0` como ejemplo real (los tags ya existen); guía para detectar instalaciones en modo copia desactualizadas + troubleshooting nuevo "el skill se comporta viejo"; desinstalación manual en loop.
  - `CONTRIBUTING.md`: `README.md` por skill ahora es regla obligatoria (con las secciones que exige el test estructural); workflow ampliado de 7 a 8 pasos con cascada documental explícita; regla de no usar rutas personales ni en ejemplos.
  - `docs/skill-promotion.md`: checklist de promoción incluye crear el `README.md` humano y la fila en `INSTALL.md`; validación menciona los tests estructurales de README.
  - `docs/architecture.md`: árbol actualizado (release.yml, test_security_audit_coverage.py, docs completos, nota "cada skill: SKILL.md + README.md + script"); modelo mental con las dos audiencias; "los 4 skills" → 9; sección nueva "Release automation" con el flujo de tag → release.
  - `RECRUITER.md`: 4 skills/1500 LOC → 9 skills/4100+ LOC; menciona release automation, la suite de 17 tests y el dogfooding de security-audit sobre su propio código (54 hallazgos SAST).
  - `SECURITY.md`: tabla de versiones soportadas — `v0.2.x` release activa, `v0.1.x` sin soporte.
  - LOC badges sincronizados con el código real: security-audit 1565→1788, md-lint-fix 359→400, pre-commit-guard 260→286, python-version-control 540→449 (README raíz + READMEs de los skills).

---

## 🎉 [0.2.0] — 2026-07-01

### ✨ Añadido (highlight)

- `skills/python-version-control/` — nuevo skill: audita drift de versión de Python entre 12+ fuentes de verdad. Primer hito de v0.2.0.
- `.github/workflows/release.yml` — automatiza publicación de releases: al pushear un tag `v*` empaqueta cada skill como zip individual + un bundle completo del toolkit y crea el GitHub Release con notas extraídas del CHANGELOG.

### 🛡️ Seguridad

- Migración de `npm` → `pnpm v11` para `md-lint-fix` y CI. Razón: campaña Shai-Hulud en npm (sept 2025 – mayo 2026, 700+ paquetes comprometidos, 14 000 secretos filtrados). pnpm v11 trae postinstall scripts bloqueados por defecto y `minimumReleaseAge=24h` — habría bloqueado todas las oleadas conocidas sin configuración. Documentado en `docs/supply-chain-security.md` con fuentes (CISA, Microsoft, Unit 42, Snyk).
- Badge "Supply chain hardened" en README + entrada en la tabla de principios.

### ✨ Añadido

- `skills/python-version-control/` — audita la coherencia de versión de Python entre 12+ fuentes de verdad: `pyproject.toml` (`requires-python`, classifiers, `target-version` de ruff/mypy/black), `Dockerfile FROM`, workflows con `actions/setup-python`, `.python-version`, `runtime.txt`, `tox.ini`, `noxfile.py`, `.pre-commit-config.yaml`. Detecta drift entre las declaraciones y propone una versión canónica. Solo lectura por defecto; `--fix <X.Y>` propone el diff y solo aplica con confirmación explícita. Modo `--json` para integrarlo desde `pre-push-guard`. Complementario a `security-audit` (que mira dependencias, no el intérprete). Primer hito de v0.2.0. Triggers: "audita versión python", "drift python", "python version control".
- `skills/web-snap/` — captura screenshots de URLs web en **Windows** usando Chrome/Edge ya instalado + `Pillow`. Sin Selenium, Playwright ni ChromeDriver. Modo single (`web_snap.py <archivo.png> <url>`) y modo batch desde JSON (`--batch jobs.json`). Trae al frente la ventana del browser vía `user32.SetWindowPos(HWND_TOPMOST→NOTOPMOST)` antes de capturar para minimizar la race con otras ventanas. Triggers: "captura pantalla", "screenshot de esta URL", "snapshot de la consola AWS", "evidencia visual de un despliegue". Nació documentando un GameDay Multi-AZ en `proyectos-aws-gitlab` y se promovió al toolkit.
- `skills/docker-compose-doctor/` — análisis estático de `compose.yml` / `docker-compose.yml`. Detecta 6 clases de problemas que el schema oficial de Compose no captura: puertos host duplicados (error), `env_file` inexistente (error), servicios sin healthcheck (warning), `depends_on` simple cuando el target tiene healthcheck (warning), imágenes `:latest` o sin tag (warning), volúmenes nombrados huérfanos (warning). Cero deps externas más allá de `pyyaml`. Triggers: "revisa el compose", "docker compose lint", "por qué no levanta este compose". Salida humana o `--json`. Exit 1 si hay errores.
- `skills/pre-push-guard/` — orquestador que corre `yaml-control` + `md-lint-fix --dry-run` + `pytest` sobre los archivos del diff (vs `origin/<branch>` + working tree + untracked) antes de un `git push`. Fail-fast con reporte unificado, exit 1 si algún paso falla. Opcionalmente se instala como git hook `pre-push` con `--install-hook` (opt-in, nunca automático; respalda hook previo como `.pre-push.bak`). Triggers: "valida antes de pushear", "pre-push", "corre todos los checks".
- `docs/supply-chain-security.md` — política frente a ataques de cadena de suministro Node, comparativa npm/pnpm/yarn, decisiones aplicadas en el repo y recomendaciones para usuarios.
- `docs/skill-promotion.md` — flujo formal de promoción de skills desde `~/.claude/skills/` (uso personal) al catálogo público del toolkit. Incluye checklist, criterio universal/específico, diagrama Mermaid del contrato con el agente y caso de despromoción. Enlazado desde README y CONTRIBUTING.
- `CHANGELOG.md`, `ROADMAP.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `SUPPORT.md`, `RECRUITER.md` — alineación con la plantilla del resto de repos del autor.
- `scripts/uninstall.ps1` — paridad con `uninstall.sh` para Windows.
- `.github/workflows/ci.yml` — CI con 3 jobs: `yaml-lint` (eat-your-own-dog-food con `yaml-control`), `markdown-lint`, `python-tests` (matriz ubuntu/windows/macOS × Python 3.11/3.12).
- `tests/test_skills_structure.py` — smoke tests (unittest, sin pytest). 8 tests que validan estructura, frontmatter y paridad de scripts.
- `docs/architecture.md` — vista en árbol, modelo mental, decisiones de diseño.

### 🐛 Corregido

- `skills/md-lint-fix/SKILL.md` no tenía frontmatter — el agente lo cargaba sin contrato declarado.
- `skills/docker-cleanup/SKILL.md` tenía un `:` sin escapar en `description:` que rompía el parser YAML — convertido a block scalar `|`.
- `skills/security-audit/SKILL.md` decía "9 capas" pero listaba 12 — corregido a 12.
- `README.md` / `INSTALL.md` tenían `<your-user>` como placeholder — sustituido por `vladimiracunadev-create`.

### 🔄 Cambiado

- `README.md` rediseñado: hero centrado con badges, catálogo en tabla HTML rica, sección de instalación con one-liner para máquinas nuevas, sección "Actualizar en cualquier equipo".
- `INSTALL.md` ampliado: prerequisitos verificables, instalación paso a paso por plataforma, sincronización entre equipos, troubleshooting con `<details>` colapsables.
- `CONTRIBUTING.md` reorganizado: workflow numerado en 7 pasos, tabla de estilo por lenguaje, sección explícita "skills que NO aceptamos".
- `.gitignore` cubre ahora `.claude/` y artefactos de coverage.

---

## 🎉 [0.1.0] — 2026-05-19

### ✨ Añadido

- Release inicial.
- 4 skills de producción: `security-audit`, `yaml-control`, `md-lint-fix`, `docker-cleanup`.
- `skills/_template/` para crear skills nuevos.
- `scripts/install.sh` + `scripts/install.ps1` + `scripts/uninstall.sh` — instaladores cross-platform basados en symlinks.
- `README.md`, `INSTALL.md`, `CONTRIBUTING.md`, `LICENSE` (MIT).

---

[Unreleased]: https://github.com/vladimiracunadev-create/claude-skills-toolkit/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/vladimiracunadev-create/claude-skills-toolkit/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/vladimiracunadev-create/claude-skills-toolkit/releases/tag/v0.1.0
