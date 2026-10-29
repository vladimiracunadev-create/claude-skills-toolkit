---
name: sync-fork
description: >-
  Sincroniza un fork con el repositorio upstream del que salió: autodetecta el
  parent real con `gh repo view --json parent` en vez de adivinarlo, añade el
  remoto `upstream` si falta, hace fetch, integra con **merge** (no rebase) para
  no reescribir el histórico de un fork compartido, y empuja al fork. Ante
  conflicto, árbol sucio o divergencia **se detiene y lo explica**: nunca hace
  force-push ni reset. Úsalo cuando el usuario diga "sincroniza el fork",
  "actualizar fork", "mi fork está atrasado", "trae los cambios del original",
  "sync fork", "update my fork", "my fork is behind", "pull changes from
  upstream", o cuando esté en un repo con relación de fork y quiera ponerse al
  día con el original. Funciona con `gh` para autodetectar, o con la URL del
  upstream a mano.
---

# sync-fork — poner un fork al día con su upstream

Un fork no recibe commits solo. Pasan semanas, el original avanza, y el fork
queda detrás justo cuando hace falta abrir un PR — que entonces llega con
conflictos o con cambios que ya estaban resueltos arriba.

Lo que hace daño aquí no es el fetch: es resolver mal el **origen de la verdad**
(adivinar la URL del upstream) y elegir mal la forma de integrar (un rebase que
reescribe lo que otros ya clonaron).

## 1 · Detectar el upstream

Por orden de preferencia:

**A. Autodetección con GitHub CLI** — lee el parent directamente de GitHub, sin
que el usuario dicte nada:

```bash
gh repo view --json parent --jq '.parent.url'
```

**B. Remoto ya configurado:**

```bash
git remote get-url upstream
```

Si existe, úsalo y salta al paso 3.

**C. Preguntar al usuario** si ninguna de las dos funciona. No inventes la URL a
partir del nombre del repo: un fork puede venir de una organización distinta de
la que sugiere el nombre.

## 2 · Añadir el remoto (solo si falta)

```bash
git remote add upstream <upstream-url>
```

Si ya existe un remoto `upstream` apuntando a **otra** URL, no lo pises: avisa y
pregunta. Ese remoto puede ser deliberado.

## 3 · Comprobar el estado antes de tocar el histórico

```bash
git status --short
git branch --show-current
```

Si el árbol está sucio, **para**: sugiere `git stash` y retoma después. Integrar
sobre cambios sin commitear convierte un conflicto de merge en una pérdida.

## 4 · Fetch

```bash
git fetch upstream
```

## 5 · Integrar con merge

```bash
git merge upstream/<rama-por-defecto>
```

La rama por defecto del upstream se averigua, no se asume:
`git remote show upstream | grep 'HEAD branch'`; como último recurso, `main` y
luego `master`.

**Merge por defecto, no rebase.** Un fork es público: alguien puede haberlo
clonado o tener un PR abierto contra él, y un rebase reescribe esos commits. Si
el usuario pide rebase explícitamente, usa `git rebase upstream/<rama>` y dilo
en el reporte.

Si `git merge` sale con código distinto de 0, **detente**: enumera los ficheros
en conflicto para que el usuario los resuelva. No fuerces, no resetees, no
abortes por tu cuenta sin decirlo.

## 6 · Empujar al fork

```bash
git push origin <rama-actual>
```

Si el push se rechaza porque la rama local está detrás de `origin`, el fork ha
divergido por su cuenta (commits hechos en la web, otra máquina, otro
colaborador). Avisa y explica las opciones; **no** hagas force-push.

## 7 · Confirmar

Reporta: cuántos commits entraron (`git rev-list --count HEAD@{1}..HEAD`), el
nuevo HEAD, y si el push salió bien. Si el merge dijo «Already up to date», dilo
tal cual: no hay nada que empujar.

## Plataformas

Son llamadas estándar a `git` y `gh`: idénticas en Bash y en PowerShell. En
Windows ejecútalas con la herramienta de PowerShell; en Linux o macOS, con Bash.

## Casos borde

- **No es un fork.** Si `gh repo view` no devuelve parent, dilo y pide la URL del
  upstream en vez de asumir una.
- **`gh` no instalado o sin sesión.** Cae al remoto `upstream` existente o a
  preguntar.
- **Árbol sucio.** Avisa y sugiere stash; no integres encima.
- **Ya al día.** Confirma y termina: no hay push.
- **Rama por defecto renombrada** (`master` → `main`) en el upstream: resuélvela
  con `git remote show`, no por convención.
- **Fork de un repo archivado o borrado.** El fetch falla; repórtalo como tal.

## Límites

- **No resuelve conflictos.** Los detecta, los enumera y se aparta: resolverlos
  es criterio humano sobre el contenido.
- **No hace force-push ni reset** en ninguna rama, ni para «arreglar» una
  divergencia. Eso lo decide el usuario.
- **No sincroniza todas las ramas**: trabaja sobre la rama actual. Varias ramas,
  varias pasadas.
- **No toca tags ni releases** del fork.
- **No audita qué trae el upstream.** Un merge incorpora código ajeno: si eso
  importa, pásalo después por `security-audit`.
- **No abre PRs** — eso es `git-push` (escenario H).
