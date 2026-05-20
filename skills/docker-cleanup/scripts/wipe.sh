#!/usr/bin/env bash
# docker-cleanup :: wipe.sh
# Vacía completamente el Docker local (containers + images + volumes +
# networks + build cache). Idempotente. Salida humana legible.
#
# Uso:
#   bash ~/.claude/skills/docker-cleanup/scripts/wipe.sh

set -u

# ── 0. Daemon check ────────────────────────────────────────────────
if ! docker info >/dev/null 2>&1; then
  echo "✗ Docker daemon no responde. Arranca Docker Desktop / systemctl start docker y reintenta." >&2
  exit 1
fi

echo "── Antes ─────────────────────────────────────────────"
docker system df
echo

# ── 1. Stop + rm containers ────────────────────────────────────────
running=$(docker ps -q)
if [ -n "$running" ]; then
  echo "→ Deteniendo $(echo "$running" | wc -l) container(s)..."
  docker stop $running >/dev/null
fi
all=$(docker ps -aq)
if [ -n "$all" ]; then
  echo "→ Eliminando $(echo "$all" | wc -l) container(s)..."
  docker rm -f $all >/dev/null
fi

# ── 2. Images ──────────────────────────────────────────────────────
imgs=$(docker images -aq | sort -u)
if [ -n "$imgs" ]; then
  echo "→ Eliminando $(echo "$imgs" | wc -l) imagen(es)..."
  docker rmi -f $imgs >/dev/null 2>&1 || true
fi

# ── 3. Named volumes ───────────────────────────────────────────────
vols=$(docker volume ls -q)
if [ -n "$vols" ]; then
  echo "→ Eliminando $(echo "$vols" | wc -l) volumen(es)..."
  for v in $vols; do
    if ! docker volume rm "$v" >/dev/null 2>&1; then
      echo "  ⚠ volumen '$v' en uso, se omite"
    fi
  done
fi

# ── 4. Custom networks (excepto bridge/host/none) ──────────────────
nets=$(docker network ls --filter type=custom -q)
if [ -n "$nets" ]; then
  echo "→ Eliminando $(echo "$nets" | wc -l) red(es) custom..."
  docker network rm $nets >/dev/null 2>&1 || true
fi

# ── 5. Build cache + dangling final ────────────────────────────────
echo "→ Limpiando build cache..."
docker builder prune -af >/dev/null
docker system prune -af --volumes >/dev/null

echo
echo "── Después ───────────────────────────────────────────"
docker system df
echo
echo "✓ Docker vacío."
