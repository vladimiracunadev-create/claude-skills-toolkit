---
name: git-push
description: >-
  Enruta una subida a GitHub al escenario correcto **después de leer el estado
  real del repo** (`git status`, `remote -v`, rama, `rev-list --left-right`), en
  vez de asumir que siempre es «commit y push»: repo sin remoto, rama sin
  upstream, rama detrás del remoto, árbol sucio, árbol limpio con commits
  pendientes, amend, tag/release y apertura de PR. Encadena los guardias del
  toolkit antes de escribir en el histórico, indexa con **rutas explícitas**
  (nunca `git add .` a ciegas), delega el tag/release en `version-bump` y jamás
  hace force-push a `main`/`master` sin confirmación. Úsalo cuando el usuario
  diga "sube mis cambios", "sube esto", "publica los cambios", "primer push",
  "crear PR", "corregir el último commit", "push", "commit and push", "create
  pull request", "amend", "push tag", "pull and push". El usuario no tiene que
  decir en qué caso está: el skill lo determina.
---

# git-push — subida a GitHub con el escenario correcto

Casi todo el daño que se hace al subir código viene de ejecutar el flujo
equivocado: hacer `git push` cuando la rama no tiene upstream, commitear sobre
un árbol que está detrás del remoto, o `--force` en `main` para «arreglar» una
divergencia. El estado del repo decide el flujo, así que primero se lee.

## Paso 0 — Leer el estado, siempre

```bash
git status --short
git remote -v
git branch --show-current
git log --oneline -3
git rev-list --count --left-right @{upstream}...HEAD 2>/dev/null || echo "no-upstream"
```

| Lo que ves | Escenario |
|---|---|
| Sin `.git` o sin remoto configurado | → **A. Repo nuevo** |
| La rama no tiene upstream (`no-upstream`) | → **B. Rama nueva** |
| Cuenta de «detrás» > 0 (lado izquierdo de `--left-right`) | → **C. Detrás del remoto** |
| Cambios sin commitear | → **D. Commit + push** |
| Árbol limpio y commits por delante | → **E. Solo push** |
| El usuario dice «amend» / «corregir el commit» | → **F. Amend** |
| El usuario menciona tag, release o un número de versión | → **G. Tag / release** |
| La rama no es `main`/`master` | → sugiere **H. Abrir PR** tras el push |

Los escenarios se encadenan (D → E → H es el caso típico).

## Paso 0.5 — Pasar los guardias antes de escribir en el histórico

Este skill no reimplementa la validación: la invoca.

- Antes de commitear (escenarios A, D, F): **`pre-commit-guard`** sobre lo
  staged.
- Antes de empujar (B, C, E, F, G): **`pre-push-guard`** sobre el diff contra
  `origin/<rama>`.

Si el guardia no está instalado, degrada con aviso y continúa — igual que hacen
los propios guardias con sus dependencias. Si un guardia **falla**, para: el
objetivo es que el fallo cueste un minuto en local en vez de un ciclo de CI.

> [!IMPORTANT]
> No pases `--no-verify` ni ninguna variante que salte los hooks, ni para
> «desbloquear» un push. Si un hook falla, el problema es lo que el hook
> encontró.

## Escenario A — Repo nuevo (sin remoto)

```bash
git init
git status --short                  # revisa QUÉ vas a subir antes de indexar
git add <rutas explícitas>          # nunca `git add .` a ciegas
git commit -m "<mensaje>"
gh repo create <nombre> --public --source=. --remote=origin --push
```

El primer commit de un repo nuevo es donde se filtran `.env`, claves y binarios
pesados, y donde cuesta más sacarlos después (quedan en el histórico). Revisa el
listado completo, confirma que hay `.gitignore`, y indexa por rutas.

`<nombre>` por defecto es el de la carpeta. **Pregunta público o privado** antes
de crear: no lo decidas tú.

## Escenario B — Rama nueva (sin upstream)

```bash
git push --set-upstream origin <rama>
```

Después ofrece abrir el PR (escenario H).

## Escenario C — Detrás del remoto

El remoto tiene commits que no están en local; integrar a ciegas produce
conflictos o pisa trabajo ajeno.

```bash
git status --short                  # si hay cambios sin commitear:
git stash                           #   guárdalos primero
git pull --rebase origin <rama>     # histórico lineal en tu propia rama
git stash pop                       # recupera
```

Si el `pull --rebase` entra en conflicto: para, enumera los ficheros y deja que
el usuario resuelva. No fuerces nada. Luego encadena a D o E.

## Escenario D — Commit + push (árbol sucio)

Lee el diff antes de redactar el mensaje:

```bash
git diff --stat
git diff --cached --stat
```

Mensaje en formato Conventional Commits — `<tipo>(<alcance>): <descripción>`,
tipos `feat`, `fix`, `refactor`, `docs`, `chore`, `test`, `style`, `build`.
Enséñaselo al usuario y espera su visto bueno; si da otro, usa el suyo.

```bash
git add <rutas explícitas>
git commit -m "<mensaje aprobado>"
```

Encadena a E.

## Escenario E — Push (árbol limpio, commits por delante)

```bash
git push origin <rama>
```

Si el push se rechaza por divergencia: **no** fuerces en `main`/`master`.
Explica la situación y ofrece `git pull --rebase` si la rama es compartida, o
`git push --force-with-lease` **solo** si es la rama propia del usuario y lo
confirma explícitamente.

## Escenario F — Amend del último commit

```bash
git add <rutas explícitas>
git commit --amend --no-edit        # --edit si hay que cambiar el mensaje
git push --force-with-lease origin <rama>
```

`--force-with-lease` y no `--force`: aborta si el remoto cambió desde el último
fetch, en vez de pisar lo que otro subió. Si la rama es `main` o `master`,
advierte que reescribir ahí es destructivo y pide confirmación explícita. Si el
commit **ya está empujado y la rama es compartida**, propón un commit nuevo en
vez del amend.

## Escenario G — Tag / release

Subir un tag es publicar una versión, y eso arrastra coherencia: badges,
manifests, documentación. Esa mitad no es de este skill.

1. Delega en **`version-bump`** la decisión de versión y la sincronización de
   los marcadores ACTUAL (conservando las referencias históricas del changelog).
2. Con el repo ya coherente y commiteado:

```bash
git tag -a <versión> -m "Release <versión>"
git push origin <versión>
gh release create <versión> --title "Release <versión>" --generate-notes
```

Pide el número de versión si no lo dieron. No inventes el salto semver: eso lo
decide el usuario o `version-bump`.

## Escenario H — Abrir PR tras el push

```bash
gh pr create --title "<título>" --body "<resumen>" --base main
```

Deriva el título de la rama (`feature/add-login` → «Add login») o del último
commit. Pregunta la rama base si no es `main`. Muestra la URL al terminar.

## Reglas del mensaje de commit

- `tipo(alcance): descripción` — minúsculas, sin punto final, máx. 72
  caracteres el asunto.
- Lee `git diff --stat` para acertar el alcance.
- Si el cambio toca muchas áreas, `chore: …` antes que inventar un alcance falso.
- Nunca mensajes genéricos («update files», «cambios», «fix»).

## Reglas de seguridad (no se saltan)

- Nunca `--force` a `main`/`master` sin confirmación explícita del usuario.
- Nunca `git reset --hard` sin avisar antes de lo que se pierde.
- Nunca `git add .` / `git add -A` a ciegas: `git status` primero, rutas después.
- Si aparecen `.env`, `*.key`, `*.pem`, `id_rsa`, `credentials*` o similares en
  el estado, avisa **antes** de indexar.
- Si un fichero supera 50 MB, avisa antes de empujar (GitHub lo rechaza) y
  sugiere Git LFS.
- Nunca `--no-verify` ni saltos de hooks.
- `gh repo create`: público o privado lo decide el usuario, no el skill.

## Límites

- **No decide la versión de un release** — eso es `version-bump`; aquí solo se
  crea y empuja el tag ya acordado.
- **No valida el contenido**: la validación es de `pre-commit-guard`,
  `pre-push-guard`, `yaml-control`, `md-lint-fix` y `python-lint-guard`. Este
  skill los encadena, no los sustituye.
- **No resuelve conflictos** ni reescribe histórico ajeno.
- **No gestiona credenciales ni tokens**: delega en `git` y `gh`.
- **No borra ramas remotas, releases ni tags.**
- **No configura protecciones de rama, secretos ni Actions** del repositorio.
- **Depende de `gh`** para crear repos, releases y PRs (escenarios A, G, H); sin
  `gh`, esas partes salen como instrucciones para el usuario.
