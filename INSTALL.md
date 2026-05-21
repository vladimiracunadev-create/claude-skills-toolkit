# 📦 Instalación

> Guía completa de instalación, verificación y desinstalación de `claude-skills-toolkit` — tanto en tu equipo principal como en máquinas nuevas / del equipo.

[![Linux](https://img.shields.io/badge/Linux-supported-2da44e?logo=linux&logoColor=white)](#linux--macos)
[![macOS](https://img.shields.io/badge/macOS-supported-2da44e?logo=apple&logoColor=white)](#linux--macos)
[![Windows](https://img.shields.io/badge/Windows-supported-2da44e?logo=windows&logoColor=white)](#windows--powershell)

---

## ⚙️ Requisitos

| Componente | Versión | Notas |
|---|---|---|
| **Python** | 3.11+ | Necesario para 3 de los 4 skills |
| **Git** | cualquiera reciente | Para clonar y para `git status` en los skills |
| **Claude Code** | opcional | Runtime agentic que carga los skills automáticamente — también funciona con cualquier runtime que lea `~/.claude/skills/` |

Verificación rápida de prerequisitos:

```bash
python --version    # >= 3.11
git --version
claude --version    # opcional
```

---

---

## ⚡ Instalación en otra máquina (one-liner)

### Linux · macOS · Git Bash

```bash
git clone https://github.com/vladimiracunadev-create/claude-skills-toolkit.git ~/claude-skills-toolkit \
  && cd ~/claude-skills-toolkit \
  && ./scripts/install.sh
```

### Windows · PowerShell

```powershell
git clone https://github.com/vladimiracunadev-create/claude-skills-toolkit.git $env:USERPROFILE\claude-skills-toolkit; `
  cd $env:USERPROFILE\claude-skills-toolkit; `
  .\scripts\install.ps1
```

Esto deja los 4 skills disponibles en `~/.claude/skills/` y el repo clonable/actualizable con un simple `git pull`.

> **Tip para equipos.** El repo en sí no contiene secretos ni configuración por-usuario, así que se puede instalar tal cual en cualquier máquina. Si tu organización mantiene un fork con skills internos adicionales, basta con cambiar la URL del `git clone`.

---

---

## 📋 Instalación paso a paso

### Linux · macOS

```bash
# 1. Clonar
git clone https://github.com/vladimiracunadev-create/claude-skills-toolkit.git ~/claude-skills-toolkit

# 2. Entrar al repo
cd ~/claude-skills-toolkit

# 3. Instalar (crea symlinks en ~/.claude/skills/)
./scripts/install.sh
```

### Windows · PowerShell

```powershell
# 1. Clonar
git clone https://github.com/vladimiracunadev-create/claude-skills-toolkit.git $env:USERPROFILE\claude-skills-toolkit

# 2. Entrar al repo
cd $env:USERPROFILE\claude-skills-toolkit

# 3. Instalar
.\scripts\install.ps1
```

### Windows · Git Bash / MINGW

Igual que Linux/macOS (usa el bloque de arriba). Funciona con la misma sintaxis bash.

> **Windows + symlinks.** El instalador crea symlinks por defecto. Para que funcionen necesitas:
>
> - **Developer Mode activo** — *Settings → Privacy & security → For developers → Developer Mode*, o bien
> - **PowerShell como administrador**.
>
> Si ninguno está disponible, `install.ps1` cae automáticamente a una **copia** del directorio (pierdes la actualización en caliente, pero el skill funciona).

---

---

## 🔄 Actualizar a la última versión

En cualquier máquina donde ya esté instalado:

```bash
cd ~/claude-skills-toolkit    # o $env:USERPROFILE\claude-skills-toolkit en Windows
git pull
```

Si la instalación es por **symlink** (default), los skills se actualizan en caliente — no hace falta reinstalar. Si está en modo copia (Windows sin Dev Mode), re-ejecuta `install.ps1` para refrescar las copias.

---

---

## 🔁 Sincronizar varios equipos

Para asegurarte de que dos máquinas tienen exactamente los mismos skills:

```bash
# En cada máquina
cd ~/claude-skills-toolkit
git pull
git rev-parse --short HEAD     # debe coincidir entre máquinas
ls ~/.claude/skills/           # debe listar los mismos 4 skills
```

Si trabajas en equipo y quieres pinear todos a un commit concreto:

```bash
git fetch --tags
git checkout v1.0.0      # o el tag que uses
```

(Los releases con tag aún no existen — están en el roadmap.)

---

---

## 🔍 Qué hace el instalador

Para cada carpeta dentro de `skills/` (excepto `_template`):

1. Crea —o reemplaza si ya existía— un symlink `~/.claude/skills/<skill>` → `<repo>/skills/<skill>`.
2. Imprime una línea por skill instalado.
3. Es **idempotente**: re-ejecutarlo no rompe nada.

### Por qué symlinks y no copias

| Acción | Con symlink | Con copia |
|---|:-:|:-:|
| `git pull` actualiza los skills | sí | requiere reinstalar |
| Editar un skill aplica en caliente | sí | no |
| Desinstalar deja el repo intacto | sí | sí |
| Funciona sin permisos especiales en Windows | no | sí |

---

---

## ✅ Verificación

### Linux · macOS · Git Bash

```bash
ls -la ~/.claude/skills/ | grep -E "security-audit|yaml-control|md-lint-fix|docker-cleanup"
```

Deberías ver **4 entradas** con flecha `->` apuntando a `claude-skills-toolkit/skills/...`.

### PowerShell

```powershell
Get-ChildItem $env:USERPROFILE\.claude\skills | Where-Object { $_.LinkType -eq "SymbolicLink" }
```

---

---

## 📚 Dependencias por skill

| Skill | Mínimo | Opcional (capas avanzadas) |
|---|---|---|
| **security-audit** | Python stdlib | `pip install bandit` · `trivy` · `grype` · `gitleaks` · `zizmor` · `hadolint` |
| **yaml-control** | `pip install pyyaml` | [`actionlint`](https://github.com/rhysd/actionlint) |
| **md-lint-fix** | Node + `pnpm add -g markdownlint-cli2` | — |
| **docker-cleanup** | `docker` CLI + bash | — |

Las dependencias opcionales **no son requeridas**: el skill detecta su ausencia, salta esa capa y deja constancia en el reporte.

---

---

## 🗑️ Desinstalación

### Linux · macOS · Git Bash

```bash
./scripts/uninstall.sh
```

### Windows · PowerShell

```powershell
.\scripts\uninstall.ps1
```

### Manual

```bash
rm ~/.claude/skills/security-audit
rm ~/.claude/skills/yaml-control
rm ~/.claude/skills/md-lint-fix
rm ~/.claude/skills/docker-cleanup
```

Los uninstallers **solo borran symlinks que apunten a este repo**. Si hay un directorio real con el mismo nombre (no es symlink), se deja en su sitio por seguridad y se avisa.

---

---

## 🔧 Troubleshooting

<details>
<summary><strong>El skill no aparece en Claude Code</strong></summary>

1. Verifica que el symlink existe: `ls -la ~/.claude/skills/`
2. Reinicia Claude Code.
3. Asegúrate de que `SKILL.md` tiene frontmatter válido (parsea con `python -c "import yaml; print(yaml.safe_load(open('SKILL.md').read().split('---')[1]))"`).

</details>

<details>
<summary><strong>Windows: <code>install.ps1</code> falló al crear symlink</strong></summary>

Activa Developer Mode o ejecuta como administrador. Si no es posible, el script cae a copia — funcional pero sin actualización en caliente.

</details>

<details>
<summary><strong>El skill se invoca pero falla con <code>ModuleNotFoundError</code></strong></summary>

Probablemente falte una dependencia opcional. Revisa la tabla de [dependencias por skill](#dependencias-por-skill).

</details>
