# Contribuir

PRs bienvenidos. Este repo busca acumular skills útiles, generales y mantenidos.

## Reglas para un skill nuevo

1. **Autónomo**: no asume paths absolutos al sistema del autor. Si el script necesita el repo del usuario, usar `Path.cwd()`.
2. **`SKILL.md` con frontmatter YAML** completo (`name` + `description` con triggers).
3. **Cero dependencias por defecto**. Si necesita herramienta externa: documentar en SKILL.md y degradar gracefully cuando no esté.
4. **Cross-platform** o documentar limitación explícita (ej. "requiere bash").
5. **Honestidad**: documentar qué NO hace y qué riesgos tiene.

## Workflow

1. Copia el template:

   ```bash
   cp -r skills/_template skills/mi-skill
   ```

2. Edita `skills/mi-skill/SKILL.md`:
   - Cambia `name`, `description` (incluyendo triggers en español + inglés)
   - Documenta cuándo usar / cuándo NO usar
   - Lista limitaciones y dependencias

3. Implementa el script en `skills/mi-skill/<nombre>.py` o `.sh`.
4. Actualiza `README.md` raíz agregando tu skill a la tabla de catálogo.
5. Si la lógica es no-trivial, agrega tests en `tests/test_<skill>.py`.
6. Abre PR.

## Estilo

- Python: ruff + line-length 120
- Bash: shellcheck-clean
- Markdown: pasa por `md-lint-fix` (eat your own dog food)
- Sin emojis decorativos en código (sí en MD del usuario final)

## Tipos de skill que valoramos

- **Productividad**: automatizan trabajo repetitivo (lint, format, scaffolding)
- **Seguridad**: audit, scan, detección de patrones
- **DevOps**: docker, k8s, CI/CD helpers
- **Refactoring**: análisis de calidad de código

## Tipos de skill que NO aceptamos

- Wrappers triviales de una herramienta sin valor añadido (ej. `ls` skill)
- Específicos de un cliente / empresa / proyecto privado
- Que requieran credenciales hardcoded
- Sin documentación de qué hace
