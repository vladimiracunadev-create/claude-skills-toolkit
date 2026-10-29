---
name: clone-repo
description: >-
  Clona un repositorio git dejando su contenido **directamente en el directorio
  actual** en vez de en un subdirectorio, preservando los ficheros ocultos que
  un copiado ingenuo se deja atrás (`.git`, `.github`, `.githooks`,
  `.gitignore`) y el histórico completo. Clona a un temporal y mueve, así que no
  duplica el `.git` de un repo grande. Antes de mover **inventaria las
  colisiones** con lo que ya hay en el directorio y pide confirmación: nunca
  borra a ciegas. Úsalo cuando el usuario diga "clona el repo aquí", "clonar
  repositorio en esta carpeta", "quiero los ficheros en este directorio, no en
  una subcarpeta", "clone a repo here", "pull repo contents into the current
  directory", o pegue una URL de GitHub/GitLab/Bitbucket dejando claro que
  quiere el contenido donde está. Cubre PowerShell y Bash.
---

# clone-repo — clonar dentro del directorio actual

`git clone <url>` crea siempre un subdirectorio. Cuando el directorio actual
*es* el destino —un worktree ya preparado, una carpeta de proyecto recién
creada, un repo que alguien clonó mal y hay que rehacer— hace falta otro flujo.

El error clásico al resolverlo a mano es perder los ficheros ocultos: un
`mv repo/* .` deja fuera `.git` (adiós histórico), `.github` (adiós CI),
`.gitignore` y `.githooks`. Este skill los mueve todos.

## Cuándo usar

- El usuario entrega una URL y quiere el contenido «aquí» / «en esta carpeta».
- El directorio actual está vacío o debe recibir el repo tal cual.
- Alguien corrió `git clone <url>` y obtuvo un subdirectorio que no quería.

## Cuándo NO usar

- Si el objetivo es un subdirectorio: eso es `git clone <url> <dir>` y no hace
  falta ningún skill.
- Si el directorio actual **ya es un repo git con trabajo propio**: mover un
  `.git` encima destruye el historial local. Detente y dilo.

## Pasos

1. **Obtén la URL** del mensaje del usuario o de `args`. Si no hay URL, pídela
   antes de tocar nada.
2. **Comprueba el destino** antes de clonar: `git rev-parse --is-inside-work-tree`
   y un listado del directorio actual incluyendo ocultos. Si el destino ya es un
   repo git, para y avisa.
3. **Crea un temporal único** para evitar colisiones.
4. **Clona en el temporal** — avisa primero si el repo es grande.
5. **Inventaria las colisiones**: qué entradas de primer nivel del repo ya
   existen en el destino. Si hay alguna, **enséñalas y pide confirmación
   explícita** antes de sobrescribir. Sin colisiones, sigue.
6. **Mueve todo**, ocultos incluidos. Mover y no copiar evita duplicar el `.git`.
7. **Limpia** el temporal, que queda vacío.
8. **Confirma**: lista las entradas de primer nivel que llegaron y la rama y el
   commit en el que quedó (`git log --oneline -1`).

## Implementación · Windows (PowerShell)

```powershell
$url    = "<REPO_URL>"
$tmpDir = Join-Path $env:TEMP "claude-clone-$(Get-Random)"

git clone $url $tmpDir
if ($LASTEXITCODE -ne 0) { throw "git clone falló" }

# Paso 5 — inventario de colisiones ANTES de mover nada.
$items     = Get-ChildItem -Path $tmpDir -Force
$colisiones = $items | Where-Object { Test-Path (Join-Path (Get-Location) $_.Name) }
if ($colisiones) {
    Write-Host "Ya existen en el destino:"
    $colisiones | ForEach-Object { Write-Host "  - $($_.Name)" }
    # No continúes sin confirmación explícita del usuario.
    throw "Colisiones detectadas: confirma antes de sobrescribir"
}

$items | ForEach-Object { Move-Item -Path $_.FullName -Destination (Get-Location) }
Remove-Item -Recurse -Force $tmpDir
```

Claves:

- `-Force` en `Get-ChildItem` es lo que hace visibles `.git`, `.github`,
  `.gitignore` y compañía. Sin él, el clon llega mutilado y en silencio.
- El inventario de colisiones corre **antes** del primer `Move-Item`: o se mueve
  todo o no se mueve nada, en vez de dejar el destino a medias.
- `Get-Location` en vez de una ruta fija: el skill funciona desde cualquier
  directorio.

## Implementación · Linux · macOS · Git Bash

```bash
url="<REPO_URL>"
tmpDir=$(mktemp -d)

git clone "$url" "$tmpDir" || exit 1

shopt -s dotglob          # los dotfiles entran en el glob

# Paso 5 — inventario de colisiones ANTES de mover nada.
colisiones=()
for item in "$tmpDir"/*; do
    [ -e "$(pwd)/$(basename "$item")" ] && colisiones+=("$(basename "$item")")
done
if [ ${#colisiones[@]} -gt 0 ]; then
    printf 'Ya existen en el destino:\n'
    printf '  - %s\n' "${colisiones[@]}"
    exit 1                # confirma con el usuario antes de sobrescribir
fi

mv "$tmpDir"/* "$(pwd)/"
rmdir "$tmpDir"
```

## Casos borde

- **Destino no vacío.** Es el caso que más daño hace. El inventario del paso 5
  lo convierte en una decisión del usuario en vez de un borrado silencioso.
- **Destino ya es un repo git.** No lo sobrescribas: ofrece clonar a un
  subdirectorio o cambiar de carpeta.
- **Repos grandes.** El clon puede tardar; avísalo antes de empezar.
- **Repos privados.** `git clone` pide credenciales como siempre; el skill no
  gestiona autenticación, deja que git la resuelva.
- **Solo el último snapshot.** Si el usuario no quiere el histórico, sugiere
  `git clone --depth 1` y ajusta.
- **Submódulos.** No se inicializan solos: si el repo los usa, hace falta
  `git submodule update --init --recursive` después.

## Límites

- **No gestiona autenticación** ni tokens: delega en git.
- **No resuelve un destino que ya es repo git** — se detiene por diseño, porque
  no hay forma segura de fusionar dos `.git` distintos.
- **No verifica la procedencia del código clonado.** Clonar es traerse código
  ajeno: trátalo como no confiable hasta revisarlo (no ejecutes sus scripts ni
  sus hooks a ciegas).
- **No mueve permisos ni ACLs especiales** más allá de lo que haga `mv` /
  `Move-Item` en esa plataforma.
- **No es atómico frente a interrupciones**: si el proceso muere a mitad del
  `mv`, parte del contenido queda en el temporal, cuya ruta se reporta.
