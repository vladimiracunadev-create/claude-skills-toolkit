---
name: docker-cleanup
description: |
  Use this skill when the user asks to wipe / empty / clean / reset Docker — typical phrasings include
  "limpia docker", "deja docker vacío", "borra todas las imágenes docker", "wipe docker",
  "docker prune todo", "vacía el docker", "reset docker". Performs a complete cleanup — stops and
  removes every container, removes every image, removes every named volume, removes every custom
  network, and clears the build cache. Default networks (bridge, host, none) are kept because
  Docker recreates them automatically. Single-action skill — no intermediate confirmations.
metadata:
  capabilities:
    - shell
disallowed-tools:
  - WebFetch
  - WebSearch
---

# docker-cleanup

When invoked, run the prepared script `scripts/wipe.sh` and report the disk space reclaimed. The script is idempotent: re-running it on an already-empty Docker is a no-op.

## Scope and permissions

| | |
|---|---|
| **Script capabilities** | `shell` |
| **What it touches** | Runs `scripts/wipe.sh`: stops and removes every container, image, named volume and custom network, and clears the build cache. |
| **What it never touches** | Leaves the default networks (`bridge`, `host`, `none`) alone and writes nothing outside Docker's own state. |
| **Tools removed** | `WebFetch`, `WebSearch` |

**It declares no `allowed-tools`**, deliberately: that field *pre-approves* tools — skipping the confirmation prompt for the turn that invokes the skill — rather than limiting them. Declaring it here would restrict nothing; it would remove the user's confirmation. `disallowed-tools` does remove tools from the pool while the skill is active, and that is where the real ceiling lives.

This skill is destructive by design and asks for no intermediate confirmation, so pre-approving its tools would remove the only brake left: the permission prompt.

---

## How to invoke

```bash
bash ~/.claude/skills/docker-cleanup/scripts/wipe.sh
```

Or on Windows (Git Bash / MINGW):

```bash
bash "$(cygpath ~)/.claude/skills/docker-cleanup/scripts/wipe.sh"
```

## What the script does, in order

1. Stops every running container.
2. Removes every container (running or not).
3. Removes every image (tagged or dangling).
4. Removes every named volume.
5. Removes every user-created network.
6. Clears the build cache.
7. Prints `docker system df` before and after.

## What it does NOT do

- Does **not** uninstall Docker.
- Does **not** touch `bridge` / `host` / `none` networks (Docker recreates them).
- Does **not** sign out of any registry; credentials stay.
- Does **not** ask for confirmation — invocation == execution. The user has already decided to wipe when they call this skill.

## Failure modes

- If Docker daemon is not running: the script exits 1 with `cannot connect to Docker daemon`. Tell the user to start Docker Desktop / `systemctl start docker` and retry.
- If a volume is in use by an external app the user forgot about: `volume in use` — the script prints which volume and continues with the rest.
