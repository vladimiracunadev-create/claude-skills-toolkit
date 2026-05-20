# 📋 Changelog

Todos los cambios notables de `claude-skills-toolkit` se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el versionado [SemVer](https://semver.org/lang/es/).

[![Keep a Changelog](https://img.shields.io/badge/changelog-Keep_a_Changelog-E05735?logo=keepachangelog)](https://keepachangelog.com)
[![SemVer](https://img.shields.io/badge/versioning-SemVer-3F4551)](https://semver.org)

---

## 🚧 [Unreleased]

### ✨ Añadido

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
