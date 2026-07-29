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
  HISTÓRICA (se conserva). Cubre también el drift de CODIFICACIÓN (mojibake):
  "símbolos especiales", "caracteres raros", "se ven mal los acentos o los emoji",
  "mÃ¡s", "ðŸ", "encoding roto". Trabaja sobre cualquier repositorio y cualquier stack.
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
| **Encoding (mojibake)** | `scripts/mojibake_probe.py` (round-trip sloppy-cp1252) | acentos y emoji del README/docs/generadores: `mÃ¡s`, `ðŸ›¡ï¸`, `Â·`, `â€"` |
| **Metadatos del remoto** | `gh api repos/<owner>/<repo>` (description, homepage, topics) | el "About" de GitHub: conteos, versión, % de cobertura, URL del sitio |

## Dimensión: metadatos del remoto (el "About" de GitHub)

Punto ciego clásico: el About **no está en el repo**, así que ningún `grep` local
lo alcanza y ninguna review de PR lo mira — pero es lo PRIMERO que lee quien
llega. Se queda stale con total impunidad. Caso real: el README decía "340
clases, 19 partes" (correcto) mientras el About seguía anunciando "330 clases,
18 partes" a todo el mundo.

```bash
gh api repos/<owner>/<repo> --jq '{description, homepage, topics}'
```

Contrasta con las mismas fuentes de verdad que el resto de dimensiones y corrige
**solo** lo que esté desincronizado (verifica antes cada número: en el caso real
el "7 certificaciones" y el "86–92% de cobertura" del About SÍ cuadraban con
`_mapeo.json`; solo mentían los conteos).

Dos cautelas al escribir:

- **No pases el texto por el shell.** Un `--description "🛡️ …más…"` puede
  corromperse en tránsito (ver trampa 1 de la dimensión de encoding) y acabas
  *metiendo* mojibake justo al arreglar la coherencia. Construye el JSON en
  Python y usa `gh api --method PATCH repos/<r> --input payload.json`.
- **Verifica releyendo de la API**, no por lo que imprimió tu consola, y con el
  texto escapado a ASCII (`unicode_escape`).

Otras superficies remotas con el mismo problema, si el proyecto las usa: el
`homepage`, los topics, la descripción del paquete en npm/PyPI, y el texto de la
release más reciente.

## Dimensión: encoding / mojibake

Es drift de codificación: nadie escribió `mÃ¡s`, se degradó solo cuando algo
decodificó UTF-8 como cp1252 y lo re-guardó como UTF-8. Los docs en español son
las víctimas naturales (acentos, `¿`, `·`, emoji). Corre siempre:

```bash
python scripts/mojibake_probe.py .          # informe
python scripts/mojibake_probe.py . --fix    # repara in situ
```

Tres trampas que cuestan tiempo real — están todas resueltas dentro del probe,
pero hay que conocerlas para no "verificar" en falso:

1. **No detectes mojibake con `grep 'Ã'`.** El patrón no-ASCII viaja por el
   shell y puede llegar corrupto, con lo que acabas buscando los *bytes del
   texto sano*: `Ã`→`C3` matchea toda vocal acentuada (`á`=`C3A1`), `ðŸ`→`F0`
   matchea todo emoji, `Â·`→`C2B7` matchea el `·` **correcto**. Resultado: grep
   "encuentra" mojibake en ficheros impecables y te manda a arreglar lo que ya
   está bien. Detecta por round-trip programático (el probe), nunca por patrón.

2. **cp1252 puro falla en silencio con los emoji.** cp1252 deja sin definir los
   bytes `81 8D 8F 90 9D`, y los emoji los llevan (VS16 `U+FE0F` → `EF B8 8F`).
   Con `encode('cp1252')` esas líneas lanzan `UnicodeEncodeError` y se quedan
   **sin reparar**: el fichero *parece* arreglado porque los acentos se
   corrigen, pero los emoji siguen rotos. Usa el mapa *sloppy* (cp1252 +
   latin-1 en esos 5 huecos), que es lo que hace el probe.

3. **Tu canal de observación miente.** Si stdout es cp1252, un `print` del texto
   reparado lo re-mangla y parece que la reparación lo rompió — cuando el fichero
   está bien. Juzga por `xxd`/hexdump o por `repr()`/`unicode_escape`, nunca por
   texto crudo impreso en consola.

Verificación de esta dimensión: el probe re-corrido debe dar `residual = 0`, los
`.py` tocados deben seguir compilando (`python -m py_compile`), y el diff debe
ser **simétrico** (mismas líneas `+` que `-`): solo cambian caracteres, no
estructura. Si un generador estaba corrupto, regenera y comprueba que su salida
reproduce el fichero reparado — eso valida el pipeline entero.

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
8. Buscar mojibake con `grep 'Ã'` y creerse el resultado: el patrón se corrompe
   en tránsito y matchea los bytes del texto SANO (`Ã`→`C3` = toda vocal
   acentuada). Da falsos positivos en ficheros impecables. Usa el probe.
9. Reparar mojibake con `cp1252` puro: arregla los acentos y deja los emoji
   rotos sin avisar (los bytes `81 8D 8F 90 9D` no existen en cp1252). Sloppy.
10. Juzgar una reparación de encoding por lo que imprime la consola: si stdout
    es cp1252 re-mangla el texto y verás "roto" algo que está bien. Usa hexdump.
11. Reparar un fichero generado y no el generador que lo emite: vuelve en el
    siguiente build. Repara la fuente y regenera para verificar.
12. Auditar solo lo que hay DENTRO del repo y dar por coherente el proyecto: el
    About de GitHub (y la descripción en npm/PyPI) no la ve ningún grep local y
    es lo primero que lee la gente. Compruebalo con `gh api`.
13. Corregir el About pasando el texto por el shell: los emoji/tildes pueden
    corromperse y acabas publicando mojibake al arreglar los conteos. JSON +
    `--input`, y verifica releyendo de la API.
