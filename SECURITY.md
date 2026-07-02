# 🔐 Política de seguridad

> Cómo reportar vulnerabilidades en `claude-skills-toolkit` y qué garantías ofrece el proyecto.

[![Responsible Disclosure](https://img.shields.io/badge/disclosure-responsible-2da44e?logo=hackthebox&logoColor=white)](https://github.com/vladimiracunadev-create/claude-skills-toolkit/security/advisories/new)
[![Response Time](https://img.shields.io/badge/ack-72h-1f6feb)](#tiempos-de-respuesta)

---

## 📌 Versiones soportadas

Solo la rama `main` recibe parches de seguridad. Si usas una versión tag-eada, actualiza antes de reportar.

| Versión | Soporte |
|---|:-:|
| `main` (HEAD) | sí |
| `v0.2.x` | sí (release activa) |
| `v0.1.x` | no — actualiza a `v0.2.x` |
| pre-`v0.1.0` | no |

---

---

## 🚨 Reportar una vulnerabilidad

**No abras un issue público para vulnerabilidades.**

Reporta de forma privada por uno de estos canales:

1. **GitHub Security Advisory** *(preferido)* — [crear advisory privado](https://github.com/vladimiracunadev-create/claude-skills-toolkit/security/advisories/new).
2. **Email** — `vladimir.acuna.dev@gmail.com` con asunto `[security] claude-skills-toolkit: <título>`.

Incluye en el reporte:

- Versión / commit afectado.
- Pasos para reproducir.
- Impacto estimado (qué puede hacer un atacante).
- Si tienes parche propuesto, adjúntalo.

### ⏱️ Tiempos de respuesta

- **Acuse de recibo**: dentro de 72 horas.
- **Diagnóstico inicial**: dentro de 7 días.
- **Parche o mitigación**: dentro de 30 días para severidad **alta/crítica**.

---

---

## 🎯 Modelo de amenaza

`claude-skills-toolkit` es un conjunto de scripts que se ejecutan **localmente** sobre el repo del usuario. No expone red, no almacena credenciales, no escribe fuera del repo actual (salvo el reporte de `security-audit` que se queda en raíz, y la caché de CISA KEV en `~/.cache/security-audit/`).

### 🛡️ Superficie de ataque considerada

- **Inputs de red** — `security-audit` consume OSV.dev, CISA KEV y EPSS via HTTPS. Las respuestas se parsean con `json.loads` (no `eval`).
- **Ejecución de subprocesos** — `git`, `gh`, `docker`, `bandit`, `trivy`, etc. Todos invocados con argumentos formados desde paths/versiones detectados (no concatenación de strings de usuario).
- **Escritura de archivos** — los skills modifican `requirements.txt`, `pyproject.toml`, `.md` y workflows YAML del repo del usuario cuando se invocan con `--apply` / `--fix`. Siempre con backup vía `git`.

### ⚠️ Riesgos conocidos

| Riesgo | Mitigación | Severidad |
|---|---|:-:|
| `security-audit --apply` sin `--verify` bumpea versiones sin correr tests, puede romper el build | Documentado explícitamente; modo `--verify` revierte si tests fallan | media |
| Un `SKILL.md` malicioso podría incluir frontmatter con instrucciones que confundan al agente | El usuario controla qué skills instala (revisión manual antes de `install.sh`) | baja |
| `docker-cleanup` borra TODOS los contenedores, volúmenes e imágenes sin confirmación | Documentado como **diseño explícito** — invocación = ejecución | aceptado |

---

---

## ✅ Buenas prácticas para usuarios

- **Revisa el `SKILL.md`** antes de instalar un skill de terceros (lectura de 1 minuto).
- **Corre `--dry-run`** antes de `--apply` cuando un skill modifica archivos.
- **Usa `security-audit --verify`** en lugar de `--apply` cuando hay tests disponibles.
- **No instales skills de forks no auditados** sin antes leer el diff con `main`.

---

---

## 🏅 Reconocimientos

Las personas que reporten vulnerabilidades válidas serán mencionadas (con su consentimiento) en el [CHANGELOG.md](CHANGELOG.md) de la versión que incluya el parche.
