# md-lint-fix

Detecta, auto-corrige y reporta errores markdownlint en archivos `.md`
modificados — antes de cualquier `git commit` o `git push`.

## IMPORTANTE — Cómo funciona desde cualquier repositorio

El script vive en `~/.claude/skills/md-lint-fix/fix-md-lint.py` pero usa
`Path.cwd()` como raíz de trabajo. Esto significa que **trabaja siempre
en el directorio donde estás parado**, no en portfolio-pages.

Desde cualquier repo, el comando es:

```bash
# Archivos .md modificados según git (uso normal pre-push)
python ~/.claude/skills/md-lint-fix/fix-md-lint.py

# Todos los .md del repo actual
python ~/.claude/skills/md-lint-fix/fix-md-lint.py --all

# Solo diagnóstico sin modificar nada
python ~/.claude/skills/md-lint-fix/fix-md-lint.py --dry-run
```

El script detecta el repo actual desde `Path.cwd()` — no importa desde
qué carpeta se llame el script.

---

## Cuándo usar este skill

- El usuario menciona errores MD031, MD034, MD040, MD032, MD024, MD028
- Antes de hacer commit/push con archivos `.md` modificados
- Después de crear o editar skills, docs o cualquier archivo markdown
- El usuario dice "arregla el lint", "corrige los markdown", "limpia los MD"

---

## Errores que resuelve automáticamente

| Código | Descripción | Solución |
|--------|-------------|----------|
| MD024 | Duplicate headings | Script propio — añade contexto del heading padre |
| MD040 | Fenced code block without language | Script propio — infiere lenguaje por contenido |
| MD031 | Blank lines around fenced code blocks | Auto-fix (`--fix`) |
| MD032 | Lists surrounded by blank lines | Auto-fix (`--fix`) |
| MD034 | Bare URL used | Auto-fix (`--fix`) — envuelve en `<>` |
| MD028 | Blank line inside blockquote | Auto-fix (`--fix`) |
| MD027 | Multiple spaces after blockquote | Auto-fix (`--fix`) |
| MD022 | Headings not surrounded by blank lines | Auto-fix (`--fix`) |
| MD026 | Trailing punctuation in heading | Auto-fix (`--fix`) |
| MD029 | Ordered list item prefix | Auto-fix (`--fix`) |
| MD030 | Spaces after list markers | Auto-fix (`--fix`) |
| MD009 | Trailing spaces | Auto-fix (`--fix`) |
| MD012 | Multiple consecutive blank lines | Auto-fix (`--fix`) |
| MD047 | Single trailing newline | Auto-fix (`--fix`) |

**No resuelve automáticamente** (requieren criterio humano):

- MD025 — múltiples headings H1 (implica reestructura)
- MD014 — `$` antes de comandos shell (decisión de estilo)
- MD042 — enlaces vacíos (requiere URL real)
- MD051 — fragmentos de enlace rotos (requiere verificar ancla)
- MD013 — line length (desactivado en la mayoría de proyectos)
- MD033 — inline HTML (depende de config del proyecto)

---

## Requisito en el repo destino

El repo donde se ejecute debe tener `markdownlint-cli2` disponible:

```bash
# Verificar si está instalado localmente
npx markdownlint-cli2 --version

# Si no está, instalar en el repo
npm install --save-dev markdownlint-cli2
```

Si el repo no tiene `markdownlint-cli2`, `npx` lo descargará automáticamente
(más lento la primera vez, funciona igual).

---

## Flujo de ejecución del script

1. Detecta `.md` en scope (modificados o todos según flag)
2. Escanea con `markdownlint-cli2` y cuenta errores iniciales
3. Corrige **MD024**: añade contexto del heading padre para desambiguar
4. Corrige **MD040**: infiere lenguaje del bloque (bash/python/json/yaml/hcl/etc.)
5. Auto-fix con `markdownlint-cli2 --fix` (14 reglas)
6. Verifica y reporta errores restantes agrupados por código de regla

---

## Referencia de reglas

Documentación oficial: <https://github.com/DavidAnson/markdownlint/blob/main/doc/Rules.md>
