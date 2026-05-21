# 🛡️ Seguridad de cadena de suministro

> **TL;DR.** El ecosistema npm sufre desde sept 2025 una campaña de gusano auto-replicante ("Shai-Hulud"). Este toolkit recomienda y usa **pnpm v11** para cualquier dependencia Node por sus **defensas activas por defecto** — los `npm install` típicos no las tienen. Esta política aplica a `md-lint-fix` y a cualquier skill futuro que dependa de paquetes Node.

---

## Por qué este documento existe

`claude-skills-toolkit` es código que se ejecuta dentro del entorno de desarrollo del usuario, con acceso a su working tree y a sus credenciales locales. Un toolkit que recomienda `npm install` sin contramedidas estaría empujando a sus usuarios hacia un vector activamente explotado. Este documento justifica las decisiones que tomamos para evitarlo.

---

## La amenaza: Shai-Hulud y sus variantes

**Shai-Hulud** es una campaña coordinada de tipo *worm* sobre el registro npm. Comenzó el 16 de septiembre de 2025 con el compromiso del paquete `@ctrl/tinycolor` y continúa activa al momento de redactar este documento (mayo 2026).

### Mecanismo del ataque

1. El atacante obtiene un token de publicación npm de un maintainer legítimo (típicamente vía phishing).
2. Publica una versión maliciosa de un paquete que el maintainer controla.
3. Cuando un desarrollador ejecuta `npm install`, el **script `postinstall`** del paquete se ejecuta automáticamente — **antes** de que la instalación termine.
4. El script:
   - Roba tokens npm/GitHub presentes en la máquina (`~/.npmrc`, variables de entorno, archivos de configuración).
   - Roba secretos de CI (`GITHUB_TOKEN`, claves cloud, etc.).
   - Publica nuevas versiones maliciosas en **los demás paquetes del maintainer comprometido** usando el token robado.
5. El ciclo se propaga: cada nuevo maintainer infectado expande el radio de impacto.

### Líneas de tiempo verificadas

| Fecha | Evento | Alcance documentado |
|---|---|---|
| **16 sept 2025** | Primera oleada (`@ctrl/tinycolor`) | CISA emite alerta nacional |
| **24 nov 2025** | "Second Coming" | **700+ paquetes**, 27 000 repos GitHub creados, **14 000 secretos filtrados** en 487 organizaciones |
| **Nov 2025** | Variante AntV | 300+ versiones maliciosas vía maintainer comprometido |
| **11 may 2026** | "Mini Shai-Hulud" (descubierto por Microsoft) | 170+ paquetes npm + 2 PyPI, 404 versiones maliciosas |
| **19 may 2026** | Grupo "TeamPCP" | 323 paquetes en una ráfaga de 22 minutos |

### Por qué los antivirus no ayudan

- El código se ejecuta **dentro del proceso `npm`** del usuario, en su contexto y con sus permisos.
- Roba secretos en memoria y los exfiltra por HTTPS a endpoints legítimos (GitHub repos creados al vuelo).
- Los paquetes maliciosos suelen estar disponibles **horas** antes de que npm los purge — el primer desarrollador que actualiza en esa ventana es la víctima.

---

## Defensas por gestor (mayo 2026)

| Defensa | npm v11.10 | **pnpm v11** | Yarn 4.10 |
|---|---|---|---|
| **Postinstall scripts bloqueados por defecto** | ❌ Opt-in (`ignore-scripts=true` rompe `sharp`, `esbuild`, `playwright`, `node-gyp`...) | ✅ **Sí desde v10** — allowlist explícito vía `allowBuilds` / `onlyBuiltDependencies` | Parcial |
| **Cuarentena de versiones nuevas** | ❌ Opt-in (`min-release-age`) | ✅ **`minimumReleaseAge=1440` (24 h) por defecto desde v11** | ✅ `npmMinimalAgeGate=3d` |
| **`trustPolicy=no-downgrade`** | ❌ | ✅ | ❌ |
| **Verificación de provenance (SLSA)** | ✅ (opt-in vía `--strict-provenance`) | ✅ | ✅ |

### Por qué la cuarentena de 24 h es decisiva

Cada oleada documentada de Shai-Hulud fue **detectada y purgada del registro npm en cuestión de horas**. Un cliente con `minimumReleaseAge=1d`:

- No puede resolver una versión hasta que tenga al menos 24 h publicada.
- Para cuando una versión es elegible, ya fue retirada si era maliciosa.
- **Habría bloqueado todas las oleadas conocidas sin configuración adicional.**

pnpm v11 lo aplica **por defecto**. Con npm requiere recordar configurarlo en cada proyecto y CI.

### Por qué `npm ignore-scripts` no es solución

Activar `ignore-scripts: true` en `.npmrc` rompe los paquetes que tienen builds nativos legítimos:

- `sharp` (procesamiento de imágenes) — no compila bindings nativos.
- `esbuild` — no descarga el binario.
- `node-gyp` consumers en general.
- `playwright`, `cypress`, `puppeteer` — no descargan navegadores.

pnpm resolvió esto con un **allowlist explícito** (`onlyBuiltDependencies` en `package.json` o `pnpm.allowedDeps`): solo los paquetes que listes pueden ejecutar lifecycle scripts. El default es deny.

---

## Decisiones aplicadas en este repo

### 1. `md-lint-fix` recomienda pnpm

Su `SKILL.md` documenta `pnpm add -D markdownlint-cli2` como instalación recomendada. Las alternativas (yarn, npm con `--ignore-scripts`) se listan con advertencia explícita.

Referencia: [skills/md-lint-fix/SKILL.md](../skills/md-lint-fix/SKILL.md)

### 2. CI usa pnpm

El workflow `markdown-lint` en [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) instala `markdownlint-cli2` con `pnpm v11` — heredando `minimumReleaseAge=1d` y postinstall bloqueado.

### 3. Actions pinneadas a SHA

Todas las GitHub Actions en este repo están pinneadas a **SHA inmutable** (no a tag), incluido `pnpm/action-setup`. Esto se valida con `yaml-control --workflows` (parte de `.github/workflows/ci.yml`). Un atacante que comprometa la cuenta del autor de una action no afecta a este repo: los SHA no cambian.

### 4. `security-audit` ya cubre `package-lock.json`

El skill [`security-audit`](../skills/security-audit/) parsea `package.json` + `package-lock.json` + `pnpm-lock.yaml` + `yarn.lock` y cruza versiones contra OSV.dev (que indexa GHSA, npm advisories y CISA KEV). Es la red de seguridad ex-post si una versión maliciosa entra al lockfile.

---

## Gotchas operacionales detectados al aplicar la política

Al migrar 5 repos públicos (mayo 2026) aparecieron 3 trampas que el playbook ingenuo no cubre:

### 1. `pnpm@11.0.0` requiere Node ≥ 22.13

pnpm v11 usa `node:sqlite`, módulo built-in introducido en Node 22.13. Repos con `setup-node` en Node 20 fallan en `Setup pnpm` con:

```
warn: This version of pnpm requires at least Node.js v22.13
Error [ERR_UNKNOWN_BUILTIN_MODULE]: No such built-in module: node:sqlite
```

**Fix:** bumpear `node-version: '22'` en todos los `actions/setup-node` y `FROM node:22-alpine` en Dockerfiles cuando migres a pnpm v11. Si necesitas Node 20 por compatibilidad, fija `pnpm@10.x` en `packageManager` y acepta que `minimumReleaseAge=1d` solo está disponible en v11+.

### 2. `version:` en `pnpm/action-setup` + `packageManager` en `package.json` = conflicto

Si declaras la versión en ambos lugares, el action aborta con `ERR_PNPM_BAD_PM_VERSION`:

```
Error: Multiple versions of pnpm specified:
  - version 11 in the GitHub Action config with the key "version"
  - version pnpm@11.0.0 in the package.json with the key "packageManager"
```

**Fix:** elige uno. `packageManager` en `package.json` es el single source of truth correcto — quita el `with: { version: ... }` del workflow.

### 3. `pnpm/action-setup` no encuentra `package.json` cuando vive en un sub-package

En repos sin `package.json` raíz (típico en monorepos: solo hay `apps/foo/package.json` o `09-foo/package.json`), el action no detecta `packageManager` y falla con `Error: No pnpm version is specified`.

**Fix:** apunta explícitamente al sub-package:

```yaml
- name: Setup pnpm
  uses: pnpm/action-setup@0e279bb959325dab635dd2c09392533439d90093 # v6.0.8
  with:
    package_json_file: apps/foo/package.json
```

### 4. Dockerfiles también necesitan migración

Si tu repo tiene Dockerfiles que copian `package-lock.json` y corren `npm ci`, **rompen al hacer build** tras la migración. El playbook estándar olvida esto.

**Fix:** patrón para `node:22-alpine` (corepack incluido):

```dockerfile
FROM node:22-alpine
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile --prod
COPY --chown=node:node . .
CMD ["pnpm", "start"]
```

---

## Recomendaciones para los usuarios del toolkit

Si tu repo consume paquetes Node:

1. **Migra a pnpm v11+.** Es la única migración con beneficio inmediato de seguridad por defecto.
2. **Pinea el gestor en `packageManager`** (en `package.json`): `"packageManager": "pnpm@11.x.x"`. Corepack lo aplicará automáticamente.
3. **No reduzcas `minimumReleaseAge`.** El default de 1 día es el que bloquea Shai-Hulud. Si tienes que reducirlo, documenta por qué.
4. **Usa `onlyBuiltDependencies`** para listar explícitamente los paquetes que necesitan ejecutar scripts (típicamente `sharp`, `esbuild`, `prisma`, `puppeteer`). Cualquier paquete que pida ejecutar scripts y no esté en la lista es una señal a investigar.
5. **Corre `security-audit` con `--layers osv,kev,epss`** después de cada `pnpm install` que cambie el lockfile.
6. **Rotar tokens npm/GitHub** si en algún momento corriste `npm install` en una máquina donde un paquete sospechoso podría haber estado durante una ventana de incidente conocido.

---

## Fuentes

- **CISA.** [Widespread Supply Chain Compromise Impacting npm Ecosystem](https://www.cisa.gov/news-events/alerts/2025/09/23/widespread-supply-chain-compromise-impacting-npm-ecosystem) — alerta oficial del gobierno de EE.UU. (sept 2025).
- **Microsoft Security.** [Shai-Hulud 2.0: Guidance for detecting, investigating, and defending against the supply chain attack](https://www.microsoft.com/en-us/security/blog/2025/12/09/shai-hulud-2-0-guidance-for-detecting-investigating-and-defending-against-the-supply-chain-attack/) (dic 2025).
- **Palo Alto Unit 42.** [Shai-Hulud Worm Compromises npm Ecosystem](https://unit42.paloaltonetworks.com/npm-supply-chain-attack/) — timeline técnico actualizado.
- **Snyk.** [Mini Shai-Hulud Hits AntV: 300+ Malicious npm Packages](https://snyk.io/blog/mini-shai-hulud-antv-npm-supply-chain-attack/).
- **pnpm.** [Mitigating supply chain attacks](https://pnpm.io/supply-chain-security) — documentación oficial de las defensas integradas.
- **Mondoo.** [npm Supply Chain Security in 2026: What Your Package Manager Does (and Doesn't) Protect You From](https://mondoo.com/blog/npm-supply-chain-security-package-manager-defenses-2026).
- **DEV Community.** [Lessons from the Spring 2026 OSS Incidents](https://dev.to/trknhr/lessons-from-the-spring-2026-oss-incidents-hardening-npm-pnpm-and-github-actions-against-1jnp).
- **SecurityWeek.** [640 NPM Packages Infected in New 'Shai-Hulud' Supply Chain Attack](https://www.securityweek.com/640-npm-packages-infected-in-new-shai-hulud-supply-chain-attack/).

---

<sub>Última revisión: 2026-05-20.</sub>
