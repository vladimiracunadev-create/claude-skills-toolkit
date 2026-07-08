---
name: repo-coherence-audit
description: >-
  Audita y reconcilia lo que la documentación y el código AFIRMAN contra fuentes
  de verdad verificables del repo — versión, conteo de tests, conteo/enumeración
  de workflows, pins de acciones a SHA, prerequisitos (Node/Python), y cualquier
  "número/afirmación de estado actual" que se desincroniza con el tiempo. Úsalo
  cuando el usuario diga "audita coherencia", "revisa que los docs cuadren",
  "hay incoherencias", "los conteos no cuadran", "la versión está desincronizada",
  "drift de versión/docs", "el README dice X pero el repo tiene Y", o
  PROACTIVAMENTE después de editar manifests, workflows, añadir/quitar tests, o
  cambiar dependencias — porque esos cambios dejan afirmaciones stale en los docs.
  Distingue SIEMPRE el marcador de estado ACTUAL (se sincroniza) de la referencia
  HISTÓRICA (se conserva). Trabaja sobre cualquier repositorio y cualquier stack.
---

# Repo Coherence Audit

## Qué hace y por qué existe

La documentación miente con el tiempo — no por mala fe, sino por deriva. Alguien
añade 5 tests y el README sigue diciendo "49 tests". Se bumpea `pyproject.toml`
pero `package.json` y el endpoint `/status` se quedan atrás. Se migra a Node 24
pero la guía de instalación sigue pidiendo Node 20. Se pinnea una acción a un SHA
nuevo pero la tabla de SHAs del SECURITY.md muestra el viejo.

Este skill reconcilia esas **afirmaciones** contra **fuentes de verdad
verificables** (el manifest canónico, `pytest --collect-only`, `ls
.github/workflows/`, los `uses:` reales, etc.). No adivina: mide y compara.

## Principio #1 — ACTUAL vs HISTÓRICO (el error que hay que evitar)

Un `grep` de un valor viejo (versión, conteo) devuelve DOS cosas mezcladas.
Clasificar mal aquí es el fallo más común y más dañino:

- **Marcador de estado ACTUAL** → se sincroniza a la verdad.
  Ej.: título de doc "— v0.10.1", campo `version` del manifest, "versión actual:
  vX", "estables a vX", comentario `# 49 tests` junto a un comando `pytest`,
  fila de "métricas actuales", tabla de SHAs "activos".

- **Referencia HISTÓRICA** → NO se toca.
  Ej.: "feature X añadida en v0.9.1", "Completado en v0.10.0", entradas de
  CHANGELOG, secciones de ROADMAP por versión, ADRs fechados, "22 → 49 tests"
  cuando describe una evolución pasada concreta, "el módulo no cambia desde vX".

Regla mental: *¿esta línea afirma cómo está el repo AHORA, o narra qué pasó en
una versión pasada?* Lo primero se corrige; lo segundo se preserva. Ante la duda,
lee la línea completa y su encabezado de sección — un número bajo "## Hitos
v0.10.0" es historia; el mismo número junto a "corre los tests" es estado actual.

Para changelog/roadmap: **añade una entrada nueva**; nunca reescribas la historia.

> **Prueba de fuego (al terminar):** un `grep` que combine un marcador de estado
> ("actual", "current", "versión actual", "estables a") con el valor VIEJO debe
> devolver **vacío**. Si algo sale, o es un marcador que olvidaste sincronizar, o
> es histórico mal fraseado.

## Flujo

Dos modos. Por defecto **report** (solo diagnostica); pasa a **fix** cuando el
usuario lo pida o cuando el arreglo sea obvio y de bajo riesgo.

1. **Reunir la verdad.** Corre `scripts/coherence_probe.py` (ver abajo) para
   obtener, de una sola pasada, los hechos verificables del repo: versiones en
   todos los manifests, lista+conteo de workflows, conteo de tests, y pins de
   acciones. Si el script no aplica a algún stack, cae a los comandos manuales
   de la tabla.
2. **Inventariar afirmaciones.** Grep de los valores relevantes en docs/código.
3. **Clasificar** cada resultado como ACTUAL o HISTÓRICO (Principio #1).
4. **Reportar** el drift encontrado: qué afirma el doc vs. la verdad, y dónde.
5. **(modo fix)** Aplicar correcciones **acotadas** (por fichero/línea), nunca un
   `sed` global ciego que pise historia. Regenerar tablas derivadas (p.ej. una
   tabla de tests por-archivo) desde la verdad, no a mano.
6. **Verificar** con la prueba de fuego + relanzar la fuente de verdad (que el
   conteo/enum ahora cuadre). Si tocaste código, corre los tests/lint.

## Dimensiones y su fuente de verdad

| Dimensión | Fuente de verdad (comando) | Marcadores ACTUALES típicos |
|---|---|---|
| **Versión** | manifest canónico del stack (abajo) | título de docs, badge/banner, `version` de otros manifests, endpoint `/status`/`--version`, "versión actual", tags de imagen de ejemplo |
| **Conteo de tests** | `pytest --collect-only -q` (Python); `vitest --run`/`jest --listTests`; `go test -list` | "N tests" junto a comandos de test, specs, tablas por-archivo, métricas |
| **Workflows** | `ls .github/workflows/*.y*ml` | "N workflows", enumeraciones ("backend, frontend, …") |
| **Pins de acciones** | los `uses: …@<sha>  # vX` reales de los workflows | tablas de "SHAs activos", ejemplos de pin, "último pin pendiente" |
| **Prerequisitos** | versión en CI (`setup-node`/`setup-python`) y `engines`/`requires-python` | "Node.js 20+", "Python 3.11+", tablas de "Runtime" |
| **Dependencias/CVEs** | lockfile / manifest | "usa X>=Y", listas de "CVEs cerrados" |

### Fuente canónica de versión por stack

| Stack | Canónico |
|---|---|
| Node | `package.json` → `version` (+ lockfile si versiona el paquete) |
| Python | `pyproject.toml` `version` / `setup.py` / `__version__` / `VERSION` |
| Rust | `Cargo.toml` `version` (+ `Cargo.lock`) |
| Go | git tags; a veces `version.go` |
| .NET | `*.csproj` `<Version>` |
| Java | `pom.xml` `<version>` / `build.gradle` `version` |
| Genérico | `VERSION`, `version.txt` |

Cuando hay varios manifests (mono-repo, front+back), decide el canónico (el del
componente que marca el release, normalmente el que ya coincide con el
CHANGELOG/tag más reciente) y sincroniza el resto a él.

## Enumeraciones: el error sutil

Un conteo puede ser correcto y la **lista** estar mal. Ej. real: "5 workflows"
(número correcto) pero la enumeración listaba `dependabot` (que es config, no
workflow) y omitía `workflow-security`. Verifica siempre la lista contra la
fuente, no solo el número. Ojo con confundir *jobs de un workflow* con
*workflows*, y *archivos de config* (dependabot.yml) con *workflows de Actions*.

## Delegación: cuando el drift de versión implica PUBLICAR

Este skill **reconcilia** versión como una afirmación más. Pero si la conclusión
es "hay que subir de versión y publicar un release" (decidir semver, taggear,
generar checksums, verificar artefactos), eso es una **acción deliberada**
distinta: usa el skill **`version-bump`** para esa mitad. Regla práctica:

- Solo alinear marcadores stale a la versión que YA es canónica → este skill.
- Elegir NEW > OLD y publicar (tag/release/artefactos) → `version-bump`.

## Higiene de commit (modo fix)

- **Nunca `git add -A` a ciegas** — puede colar ficheros no relacionados o
  sensibles. Usa **rutas explícitas** y revisa `git status` antes de commitear.
- Un commit por tema coherente (p.ej. "alinear versión", "corregir conteos") con
  mensaje que aclare **qué se sincronizó** y que **lo histórico se conserva**.
- Si tocaste workflows, valida (`actionlint`); si tocaste código, corre tests.

## Checklist

- [ ] Verdad reunida (probe corrido o comandos manuales por dimensión)
- [ ] Afirmaciones inventariadas y clasificadas ACTUAL vs HISTÓRICO
- [ ] Drift reportado (afirma-vs-real, con fichero:línea)
- [ ] (fix) Correcciones acotadas; tablas derivadas regeneradas desde la verdad
- [ ] Prueba de fuego (grep "estado+valor viejo") → vacío
- [ ] Fuente de verdad re-verificada (conteo/enum cuadra)
- [ ] Código tocado → tests/lint verdes; commit con rutas explícitas

## Errores reales a no repetir

1. Bumpear una entrada de CHANGELOG histórica y romper la trazabilidad.
2. Dejar el título/README/roadmap con la versión vieja como "actual".
3. Corregir el número de una tabla pero no regenerar las filas (queda una tabla
   que no suma al total).
4. Contar bien pero enumerar mal (jobs≠workflows, config≠workflow).
5. `sed` global de un valor que también aparece en contexto histórico.
6. Afirmar "coherente" sin correr la prueba de fuego ni re-verificar la verdad.
7. Olvidar los marcadores no-obvios: endpoint de versión en runtime, tags de
   imagen Docker de ejemplo, comentarios `# N tests` junto a comandos.
