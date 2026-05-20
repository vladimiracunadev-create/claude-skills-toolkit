# Instalación

## Requisitos mínimos

- Python 3.11+
- Git
- (Opcional) [Claude Code](https://claude.com/claude-code) o runtime agentic compatible que cargue skills desde `~/.claude/skills/`

## Instalación rápida (Linux / macOS)

```bash
git clone https://github.com/<your-user>/claude-skills-toolkit.git ~/claude-skills-toolkit
cd ~/claude-skills-toolkit
./scripts/install.sh
```

## Instalación rápida (Windows)

PowerShell:

```powershell
git clone https://github.com/<your-user>/claude-skills-toolkit.git $env:USERPROFILE\claude-skills-toolkit
cd $env:USERPROFILE\claude-skills-toolkit
.\scripts\install.ps1
```

Git Bash / MINGW:

```bash
git clone https://github.com/<your-user>/claude-skills-toolkit.git ~/claude-skills-toolkit
cd ~/claude-skills-toolkit
./scripts/install.sh
```

> **Nota Windows**: para crear symlinks necesitas **modo desarrollador** activo (Settings → Privacy & security → For developers → Developer Mode) o ejecutar como administrador. Si no, el script cae a copia (no symlink).

## Qué hace el instalador

Para cada carpeta en `skills/`:

1. Crea (o reemplaza) un symlink `~/.claude/skills/<skill>` → `<repo>/skills/<skill>`
2. Imprime el resultado por skill

Esto permite:

- `git pull` actualiza todos los skills sin reinstalar
- Editas un skill en el repo y el cambio aplica al instante en Claude Code
- Desinstalar = `rm ~/.claude/skills/<skill>` (no afecta el repo)

## Verificación

```bash
ls -la ~/.claude/skills/ | grep -E "security-audit|yaml-control|md-lint-fix|docker-cleanup"
```

Deberías ver 4 entries con flecha `->` apuntando a `claude-skills-toolkit/skills/...`.

## Dependencias por skill

| Skill | Mínimo | Opcional (capas avanzadas) |
|---|---|---|
| **security-audit** | `pip install pyyaml` (ya viene en stdlib parcial) | `pip install bandit` / `trivy` / `grype` / `gitleaks` / `zizmor` / `hadolint` |
| **yaml-control** | `pip install pyyaml` | `actionlint` |
| **md-lint-fix** | Node + `npm install -g markdownlint-cli` | — |
| **docker-cleanup** | `docker` CLI | — |

## Desinstalar

```bash
./scripts/uninstall.sh   # quita los symlinks; el repo queda intacto
```

O manualmente:

```bash
rm ~/.claude/skills/security-audit
rm ~/.claude/skills/yaml-control
rm ~/.claude/skills/md-lint-fix
rm ~/.claude/skills/docker-cleanup
```
