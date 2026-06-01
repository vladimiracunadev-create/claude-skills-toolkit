# 📋 Changelog

Todos los cambios notables de `claude-skills-toolkit` se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el versionado [SemVer](https://semver.org/lang/es/).

[![Keep a Changelog](https://img.shields.io/badge/changelog-Keep_a_Changelog-E05735?logo=keepachangelog)](https://keepachangelog.com)
[![SemVer](https://img.shields.io/badge/versioning-SemVer-3F4551)](https://semver.org)

---

## 🚧 [Unreleased]

### 🛡️ Seguridad

- Migración de `npm` → `pnpm v11` para `md-lint-fix` y CI. Razón: campaña Shai-Hulud en npm (sept 2025 – mayo 2026, 700+ paquetes comprometidos, 14 000 secretos filtrados). pnpm v11 trae postinstall scripts bloqueados por defecto y `minimumReleaseAge=24h` — habría bloqueado todas las oleadas conocidas sin configuración. Documentado en `docs/supply-chain-security.md` con fuentes (CISA, Microsoft, Unit 42, Snyk).
- Badge "Supply chain hardened" en README + entrada en la tabla de principios.

### ✨ Añadido

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

[Unreleased]: https://github.com/vladimiracunadev-create/claude-skills-toolkit/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/vladimiracunadev-create/claude-skills-toolkit/releases/tag/v0.1.0
