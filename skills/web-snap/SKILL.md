---
name: web-snap
description: Captura screenshots de URLs web en Windows usando Chrome/Edge + Pillow, sin Selenium ni Playwright. Úsalo cuando el usuario pida "captura pantalla", "screenshot de esta URL", "snapshot de la consola AWS/Azure/GCP", "documentar con capturas", "evidencia visual", "generar PNGs de la web", o cuando necesites tú mismo dejar evidencia visual de un despliegue/demo en un proyecto. Genera PNG en directorio configurable, soporta modo single y modo batch desde JSON. Solo Windows con sesión interactiva.
---

# web-snap

Skill para capturar pantallas de URLs web en **Windows** usando Chrome o Edge ya instalados + `Pillow`. Sin dependencias pesadas (Selenium, Playwright, ChromeDriver, etc).

## Cuándo invocarlo

- El usuario pide capturas de una URL específica.
- Necesitas generar evidencia visual de una consola web (AWS, Azure, GCP, GitLab, GitHub, Datadog, Grafana, etc) para documentar un despliegue.
- Estás cerrando un caso/lab y quieres incluir screenshots reproducibles en `VISUALIZATION.md` o similar.
- El usuario quiere "documentar paso a paso con capturas" un flujo manual.

## Cuándo NO invocarlo

- Si la app es una preview local servida en un puerto → usa `mcp__Claude_Preview__preview_screenshot` (más limpio, sin barra de tareas).
- Si necesitas capturas de elementos específicos del DOM o esperar a que un selector aparezca → usa Playwright/Selenium, no este skill.
- Si no estás en Windows → este skill no funciona (depende de `user32.dll`).

## Requisito previo (una sola vez por máquina)

```bash
pip install pillow
```

Chrome o Edge ya deben estar instalados.

## Modo single — 1 captura

```bash
python ~/.claude/skills/web-snap/web_snap.py <archivo.png> "<URL>" --wait 6 --out ./img
```

- `<archivo.png>` — nombre del PNG resultante.
- `"<URL>"` — URL completa entre comillas.
- `--wait N` — segundos antes de capturar (default 6). Subir a 10-15 para consolas AWS pesadas.
- `--out DIR` — directorio de salida (default `./img`, se crea si no existe).
- `--browser chrome|edge` — default `chrome`.

## Modo batch — N capturas en una pasada

Crea `jobs.json`:

```json
[
  {"file": "01-cluster.png",      "url": "https://us-east-2.console.aws.amazon.com/ecs/v2/clusters", "wait": 10},
  {"file": "02-target-group.png", "url": "https://us-east-2.console.aws.amazon.com/ec2/home?region=us-east-2#TargetGroups:", "wait": 8},
  {"file": "03-dashboard.png",    "url": "https://us-east-2.console.aws.amazon.com/cloudwatch/home", "wait": 12}
]
```

```bash
python ~/.claude/skills/web-snap/web_snap.py --batch jobs.json --out ./caso-x/img
```

## Verificación post-captura

```bash
python ~/.claude/skills/web-snap/web_snap.py --list --out ./caso-x/img
```

Lista los PNGs con su tamaño en KB. Si alguno está < 50 KB probablemente quedó en blanco — re-tomarlo con `--wait` mayor.

**Importante:** después de cada captura, usa la herramienta `Read` sobre el PNG para validar visualmente que efectivamente capturó la URL correcta y no otra ventana (Explorador, Claude Code, terminal). Si capturó la ventana incorrecta, re-toma con `--wait` mayor.

## Flujo típico cuando documentas un caso

1. **Verificar el método antes de empezar.** Toma 1 captura de prueba sobre cualquier URL conocida y léela con `Read`. Si el PNG sale en blanco o muestra la ventana incorrecta, ajusta antes de la sesión real.
2. **Hacer todas las capturas en batch.** Una vez levantado el stack/demo, lanza `--batch jobs.json` con todas las URLs.
3. **Validar cada PNG con `Read`.** Re-tomar las que salieron mal.
4. **Referenciar en Markdown** con `![descripción](./img/archivo.png)`.

## Limitaciones conocidas

| Limitación | Workaround |
|---|---|
| Captura toda la pantalla (incluye barra de tareas, otras ventanas) | Maximizar Chrome antes / cerrar otras ventanas |
| `--wait` es heurístico | Subir a 10-15s para consolas web pesadas (AWS, Azure) |
| Race condition: a veces captura otra ventana | El script usa `SetWindowPos(HWND_TOPMOST)` para minimizar — pero si falla, re-tomar |
| Solo Windows interactivo | No funciona en headless ni en SSH/RDP cerrado |
| No espera selectores específicos del DOM | Usar Playwright si necesitas eso |

## Filosofía

Este skill **prioriza simplicidad sobre robustez**. La idea es: "tengo Chrome abierto, quiero un PNG de esta URL ya". No es Playwright; no pretende serlo. Si necesitas algo más serio (CI headless, esperar a un selector, evitar capturar otras ventanas), usa Playwright.

## Historial

Nació en `caso-m-resiliencia-failover/scripts/snap.py` del repo `proyectos-aws-gitlab` (2026-06-01) para documentar un GameDay Multi-AZ con evidencia auditable. Se promovió a `~/.claude/skills/web-snap/` y luego al toolkit para reusarse en cualquier proyecto.
