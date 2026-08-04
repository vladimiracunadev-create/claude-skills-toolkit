---
name: version-bump
description: >-
  Control de cambio de versión GENERAL para cualquier repositorio (Rust/Cargo,
  Node/npm, Python, Go, .NET, Java, o proyectos sin gestor). Úsalo cuando el
  usuario pida subir/cambiar la versión, preparar o publicar un release, o
  cuando sospeche incoherencias de versión entre código, manifests, docs y web.
  REGLA CRÍTICA — distinguir SIEMPRE los marcadores de "versión actual" (se
  bumpean) de las referencias HISTÓRICAS de changelog (se conservan);
  `version_probe.py` hace esa clasificación de forma determinista en vez de
  dejarla al criterio del agente. Verificar cada paso con comandos reales antes
  de afirmar que está hecho.
---

# version-bump — control de versión general

Objetivo: cambiar la versión de un producto de forma **coherente en TODO el
repositorio** y, si aplica, publicar el release verificándolo. Sirve para
cualquier stack. No asume ninguna herramienta concreta hasta detectarla.

---

## Principio #1 — actual vs histórico (el error más común)

Un `grep` de la versión vieja devuelve DOS cosas mezcladas:

- **Marcadores de versión ACTUAL** → hay que bumpearlos.
  (badge/banner del README, campo del manifiesto, "versión actual" del roadmap,
  versión en la landing, sample outputs, `--version`.)
- **Referencias HISTÓRICAS** → NO se tocan.
  ("Entregado en v0.13", "version bump a 0.13.0" dentro de la sección de esa
  versión, entradas de CHANGELOG, "Completado en vX".)

Para el changelog/roadmap: **añade una entrada NUEVA** para la versión nueva y
marca la anterior como "entregada"; nunca reescribas la historia.

### `version_probe.py` — la regla, en código

No dejes esta clasificación al ojo. El script la resuelve y marca lo que no
puede decidir:

```bash
python ~/.claude/skills/version-bump/version_probe.py --old 0.2.0
```

Clasifica cada aparición en tres cubos:

| Cubo | Significado | Acción |
|---|---|---|
| `ACTUAL` | Badge, campo de manifest, `--version`, "versión actual", encabezado de roadmap | **Se bumpea** |
| `HISTORICO` | Entrada de CHANGELOG, "entregado en vX", "released in", enlaces de comparación | **Se conserva** |
| `AMBIGUO` | Sin señal concluyente | **Revisión humana** — el script no adivina |

Reglas que aplica, en orden:

1. En ficheros `CHANGELOG` / `HISTORY` / `RELEASES` / `NEWS`, **todo es
   histórico** salvo la sección `Unreleased`.
2. En manifests (`package.json`, `pyproject.toml`, `Cargo.toml`, `*.csproj`,
   `pom.xml`, `VERSION`…), el campo de versión es **actual** por definición.
3. Señales **inequívocas** de presente (badge `shields.io`, `__version__`,
   `"version":`, `<Version>`, `--version`) ganan a cualquier otra cosa — un
   badge que enlaza a `CHANGELOG.md` sigue siendo estado actual.
4. Señales de pasado (`entregado`, `released in`, `since v`, `added in`).
5. Señales débiles de presente (`versión actual`, `en curso`).
6. Encabezados: en `ROADMAP`/`PLAN` son estado; en el resto, ambiguos.

> **Prueba de fuego automatizada** al terminar el bump:
>
> ```bash
> python ~/.claude/skills/version-bump/version_probe.py --verify --old 0.2.0 --new 0.3.0
> ```
>
> Exit `1` si algún marcador ACTUAL sigue mostrando la versión vieja.

---

## Paso 0 — Semver y alcance

Confirma el salto con el usuario si no es obvio:

- **patch** (x.y.**Z**): bugfixes compatibles.
- **minor** (x.**Y**.0): features compatibles.
- **major** (**X**.0.0): cambios incompatibles.

Define `OLD` y `NEW` (ej. `OLD=0.13.0`, `NEW=0.14.0`).

---

## Paso 1 — Detectar la fuente de verdad de la versión

`version_probe.py` sin argumentos ya reporta la versión canónica de cada
manifest de la raíz y avisa si **no coinciden entre sí**:

```bash
python ~/.claude/skills/version-bump/version_probe.py
```

| Stack | Fuente canónica |
|---|---|
| Rust | `Cargo.toml` → `version = "..."` (y `Cargo.lock` si versiona el propio crate) |
| Node | `package.json` → `"version"` (+ `package-lock.json` / `npm-shrinkwrap.json`) |
| Python | `pyproject.toml` `version`, o `setup.py`, o `__init__.py::__version__`, o `VERSION` |
| Go | normalmente **solo git tags**; a veces `version.go` o `-ldflags -X` |
| .NET | `*.csproj` → `<Version>` / `<AssemblyVersion>`; a veces `Directory.Build.props` |
| Java | Maven `pom.xml` `<version>`; Gradle `build.gradle(.kts)` `version =` |
| Genérico | fichero `VERSION`, `version.txt`, header de shell/Makefile |

---

## Paso 2 — Inventariar TODAS las ocurrencias

```bash
python ~/.claude/skills/version-bump/version_probe.py --old "$OLD" --json > /tmp/probe.json
```

Clasifica cada resultado en:

1. **Canónico** (paso 1).
2. **Manifests / distribución**: scoop `.json`, winget `.yaml`, chocolatey `.nuspec`,
   Homebrew formula, AUR `PKGBUILD`, Snap, Flatpak, `Chart.yaml`, imágenes Docker,
   `package.json`. (Ojo: muchos usan `$version`/`latest` en la URL → solo el
   campo versión cambia.)
3. **Docs de estado actual**: badge/banner del README, "versión actual" del
   ROADMAP/PLAN, tabla de soporte de `SECURITY.md`.
4. **Web/landing**: badge de versión, botón de descarga, sección de evolución.
5. **Muestras / fixtures**: outputs de ejemplo, snapshots de tests, capturas.
6. **Histórico** → **no tocar** (ver Principio #1).

---

## Paso 3 — Aplicar el bump

- Cambia el canónico y **regenera lockfiles** si contienen la versión propia
  (`cargo update -p <crate>` / `npm install` para refrescar `*-lock`).
- Bump de cada manifiesto y de cada marcador de estado actual.
- Web: badge + botón + añade/extiende la sección de changelog a `NEW`.
- Changelog/roadmap: **entrada nueva** para `NEW`; la anterior pasa a "entregada".
- Muestras de `--version` u outputs de ejemplo que muestren la versión.

Usa reemplazos **acotados** (por fichero/línea). Evita un `sed` global ciego que
pise referencias históricas.

---

## Paso 4 — Verificar coherencia (obligatorio, con salida real)

```bash
python ~/.claude/skills/version-bump/version_probe.py --verify --old "$OLD" --new "$NEW"
```

Debe reportar `✓` en ambas comprobaciones. Complementa con
[`repo-coherence-audit`](../repo-coherence-audit/SKILL.md) para el resto de
afirmaciones de los docs (conteos, workflows, prerequisitos).

Compila/valida si el stack lo permite (`cargo build` / `npm run build` /
`pytest`…). Si el entorno local no compila, deja constancia y confía en CI —
pero NO afirmes "listo" sin evidencia.

---

## Paso 5 — Commit limpio (evita accidentes)

- **NUNCA `git add -A` a ciegas.** Puede colar ficheros no relacionados o
  sensibles (capturas con datos reales, credenciales, artefactos). Usa rutas
  explícitas:

  ```bash
  git add <fichero-canónico> <manifests...> README.md docs/... web/...
  git status                # revisa qué queda fuera a propósito
  ```

- **Repos públicos**: no commitees imágenes/logs/fixtures con datos personales
  (usuario, rutas, IPs, PIDs, tokens). Si ya se coló y es el commit tip recién
  pusheado, rehazlo (`git reset --soft HEAD~1` → re-stage selectivo →
  `git commit` → `git push --force-with-lease`).
- Mensaje claro que liste qué se bumpeó y aclare que lo histórico se conserva.

---

## Paso 6 — Tag y release (si el proyecto publica)

1. Confirma que **CI de la rama está verde** antes de etiquetar.
2. Averigua el mecanismo de release:
   - CI se dispara con el **tag** (`on: push: tags: v*`) → solo `git tag vNEW &&
     git push origin vNEW` y CI compila+publica.
   - Manual → construye artefactos y `gh release create` / equivalente.
3. **Descarga artefactos por run/tag EXPLÍCITO, no "latest"** — "latest" puede
   resolver a un run viejo o en curso y darte un binario incorrecto.
4. **Checksums**: el fichero de hashes debe listar los **basenames reales** de
   los assets (no rutas internas de CI tipo `build\...`). Verifícalo:

   ```bash
   sha256sum -c SHA256SUMS.txt     # todos OK
   ```

5. Verifica el binario publicado: `--version` == `NEW` y sin hacks de debug.

---

## Paso 7 — Verificación final (no afirmar sin evidencia)

```bash
gh release view vNEW --json assets --jq '.assets[]|.name+" — "+(.size|tostring)+" B"'
```

- Web/landing en vivo muestra `NEW` (fetch de la URL pública).
- Manifests de distribución (scoop/winget/choco) con `NEW` y hashes actualizados.

> ⚠️ `gh` muestra los tamaños en KB con truncamiento: un asset de 700 B se ve
> como "0 KB". Compara **bytes**, no la vista formateada.

---

## Qué NO hace / limitaciones

- **`version_probe.py` no modifica nada.** Es solo lectura: clasifica y verifica.
  Aplicar el bump es trabajo del agente, con reemplazos acotados.
- **No adivina lo ambiguo.** Lo que no tiene señal clara se reporta como
  `AMBIGUO` para revisión humana, en vez de arriesgar una clasificación mala.
- **No distingue un badge real de un badge citado como ejemplo.** Una línea de
  documentación que *muestra* la sintaxis `[![Version](https://img.shields.io/…)]`
  se clasifica como `ACTUAL`, porque textualmente es indistinguible de una real.
  Produce falsos positivos en docs que explican el propio versionado — se
  detecta a simple vista en el listado, pero conviene saberlo antes de tratar la
  salida de `--verify` como un veredicto ciego.
- No lee ficheros binarios ni mayores de 2 MB.
- No conoce convenciones de versionado propias (fechas, build numbers): asume
  que la cadena que le pasas es la que hay que buscar.

---

## Dependencias

| Dependencia | Cómo instalar | Requerida u opcional |
|---|---|---|
| `python>=3.11` | viene con el SO | requerida (usa `tomllib`) |
| `gh` | <https://cli.github.com/> | opcional — solo para el paso de release |

---

## Checklist rápido

- [ ] `OLD`/`NEW` y salto semver acordados
- [ ] `version_probe.py` sin drift entre manifests
- [ ] Fuente canónica + lockfiles bumpeados
- [ ] Todos los manifests/distribución bumpeados
- [ ] Marcadores de estado (README, ROADMAP, SECURITY, web) → `NEW`
- [ ] Changelog: entrada NUEVA; histórico intacto
- [ ] `version_probe.py --verify` en verde
- [ ] Cero apariciones `AMBIGUO` sin revisar
- [ ] Commit con rutas explícitas; sin ficheros sensibles
- [ ] CI verde → tag → release; artefactos por run/tag explícito
- [ ] Checksums con basenames reales y `-c` OK
- [ ] Binario/web publicados verificados con salida real

---

## Errores reales a no repetir

1. Bumpear una entrada de changelog histórica y romper la trazabilidad.
2. Dejar la landing/README/roadmap con la versión vieja como "actual".
3. `git add -A` que cuela capturas con datos personales a un repo público.
4. Fichero de checksums con rutas internas de CI → `sha256sum -c` falla.
5. Descargar "latest" y publicar un binario de la versión anterior.
6. Afirmar "release publicado" sin ver los assets con tamaño real (> 0 bytes).
7. Olvidar los lockfiles (`Cargo.lock` / `package-lock.json`) cuando versionan el paquete.
