# 🆘 Soporte

> Cómo obtener ayuda con `claude-skills-toolkit`, según el tipo de problema.

[![Issues](https://img.shields.io/github/issues/vladimiracunadev-create/claude-skills-toolkit?logo=github)](https://github.com/vladimiracunadev-create/claude-skills-toolkit/issues)
[![Discussions](https://img.shields.io/badge/discussions-open-2da44e?logo=github)](https://github.com/vladimiracunadev-create/claude-skills-toolkit/discussions)

---

## 🔎 Antes de pedir ayuda

1. Lee el [README](README.md) y el [INSTALL.md](INSTALL.md) — la mayoría de problemas de instalación están documentados ahí.
2. Revisa el `SKILL.md` del skill que falla — cada uno tiene su propia sección de limitaciones y troubleshooting.
3. Busca en [issues cerrados](https://github.com/vladimiracunadev-create/claude-skills-toolkit/issues?q=is%3Aissue+is%3Aclosed) — puede que tu problema ya esté resuelto.

---

---

## 📞 Canales por tipo de problema

| Tipo de problema | Canal | Tiempo de respuesta |
|---|---|:-:|
| **Bug reproducible** | [Issues — Bug report](https://github.com/vladimiracunadev-create/claude-skills-toolkit/issues/new?labels=bug) | 1-3 días |
| **Sugerir un skill nuevo** | [Issues — Proposal](https://github.com/vladimiracunadev-create/claude-skills-toolkit/issues/new?labels=proposal:skill) | 1 semana |
| **Pregunta de uso** | [Discussions](https://github.com/vladimiracunadev-create/claude-skills-toolkit/discussions) | 1 semana |
| **Vulnerabilidad de seguridad** | [SECURITY.md](SECURITY.md) — **no abrir issue público** | 72 h acuse |
| **PR / contribución** | [Pull requests](https://github.com/vladimiracunadev-create/claude-skills-toolkit/pulls) — ver [CONTRIBUTING.md](CONTRIBUTING.md) | 1 semana review |

---

---

## ✍️ Cómo escribir un buen bug report

Un buen report ahorra horas de ida-y-vuelta. Incluye al menos:

### 1. Entorno

```text
SO:        Windows 11 / Ubuntu 22.04 / macOS 14
Shell:     PowerShell 5.1 / bash 5.2 / zsh 5.9
Python:    3.11.7
Git:       2.43.0
Skill:     security-audit
Commit:    git rev-parse HEAD
```

### 2. Comando exacto que falló

```bash
python ~/.claude/skills/security-audit/security_audit.py --layers all --apply
```

### 3. Salida observada vs esperada

- Lo que salió por consola (copiar-pegar, no captura).
- Lo que esperabas que pasara.

### 4. Pasos para reproducir

Idealmente sobre un repo público o un mínimo reproducible.

---

---

## 🚫 Lo que NO es soporte

- **No damos consultoría individual** sobre arquitectura de tus skills propietarios. Para eso abre un issue de discusión pública para que toda la comunidad se beneficie.
- **No respondemos por DM** salvo para vulnerabilidades de seguridad ([SECURITY.md](SECURITY.md)).
- **No mantenemos forks privados.** Si necesitas customización profunda, fork el repo y mantén tus skills.

---

---

## 📧 ¿Y si nada de esto funciona?

Email directo al mantenedor: **[vladimir.acuna.dev@gmail.com](mailto:vladimir.acuna.dev@gmail.com)**. Úsalo como **último recurso** — los canales públicos son más rápidos porque cualquier contribuyente puede responder.
