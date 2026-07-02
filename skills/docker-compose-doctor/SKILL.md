---
name: docker-compose-doctor
description: Diagnostica problemas comunes en archivos compose.yml / docker-compose.yml antes de levantar el stack. Detecta puertos host duplicados entre servicios, servicios sin healthcheck, depends_on que no usa condition service_healthy, imágenes sin tag o pinneadas a `:latest`, volúmenes nombrados declarados pero no referenciados, y env_file apuntando a archivos inexistentes. Úsalo cuando el usuario diga "revisa el compose", "valida docker-compose", "qué tiene mal este compose", "docker compose lint", "auditar compose.yml", "chequea el stack", "por qué no levanta este compose", o proactivamente después de editar cualquier archivo `compose*.y*ml` / `docker-compose*.y*ml`. Trabaja sobre `Path.cwd()` — funciona en cualquier repo. Cero deps externas más allá de `pyyaml`.
---

# docker-compose-doctor

Diagnostica problemas comunes en archivos `compose.yml` / `docker-compose.yml` **antes** de hacer `docker compose up` — para que el stack levante a la primera y los servicios queden saludables.

No reemplaza a `docker compose config` (que valida sintaxis del schema). Cubre la capa de **convenciones operacionales** que el schema oficial no captura: healthchecks faltantes, dependencias sin esperar a `service_healthy`, etc.

---

## Cuándo invocar este skill

Triggers explícitos:

- "revisa el compose"
- "valida docker-compose"
- "qué tiene mal este compose"
- "docker compose lint"
- "auditar compose.yml"
- "chequea el stack"
- "por qué no levanta este compose"
- "doctor del compose"

Triggers proactivos:

- Después de editar cualquier `compose*.y*ml` o `docker-compose*.y*ml` en la sesión.
- Antes de un `docker compose up` cuando el usuario menciona problemas de orden de arranque, servicios "unhealthy", o puertos en conflicto.

---

## Cómo se invoca

Sin argumentos: busca `compose.yml`, `compose.yaml`, `docker-compose.yml` y `docker-compose.yaml` en `Path.cwd()` recursivamente hasta 3 niveles.

```bash
python ~/.claude/skills/docker-compose-doctor/docker_compose_doctor.py
```

Modos:

```bash
# Archivo específico
python .../docker_compose_doctor.py path/to/compose.yml

# Solo errores (omite warnings)
python .../docker_compose_doctor.py --errors-only

# Output JSON (para integraciones)
python .../docker_compose_doctor.py --json

# Verbose — muestra cada check ejecutado
python .../docker_compose_doctor.py -v
```

Exit codes:

- `0` — sin hallazgos o solo warnings.
- `1` — al menos un error (bloquea CI / pre-push).
- `2` — error de invocación (archivo no existe, YAML malformado).

---

## Qué chequea exactamente

| # | Check | Severidad | Razón |
|---|---|:-:|---|
| 1 | **Puertos host duplicados** entre servicios (`"8080:80"` en dos servicios). | error | El segundo servicio falla al bindear → stack no levanta. |
| 2 | **Servicios sin `healthcheck`**. | warning | Sin healthcheck, `depends_on: condition: service_healthy` no funciona y el orquestador no detecta servicios atascados. |
| 3 | **`depends_on` simple cuando el target tiene healthcheck**. Detecta `depends_on: [db]` cuando `db` define un healthcheck — debería usar la forma extendida con `condition: service_healthy`. | warning | Race condition clásica: la app arranca antes de que la DB acepte conexiones. |
| 4 | **Imágenes con `:latest`** o **sin tag** (ej. `image: postgres`). | warning | Builds no reproducibles. Pinnear a versión major.minor al menos. |
| 5 | **Volúmenes nombrados declarados pero no referenciados** en ningún servicio. | warning | Dead config. Suelen quedar tras refactors. |
| 6 | **`env_file` apuntando a archivo inexistente** (relativo al `compose.yml`). | error | Falla en `up`. Frecuente cuando `.env.example` se renombra. |

---

## Qué NO hace / limitaciones

- **No valida el schema de Compose**. Para eso usa `docker compose config -q` — este skill asume que la sintaxis ya es válida.
- **No ejecuta el stack**. Es análisis estático del YAML; no detecta problemas que solo aparecen runtime (ej. health check que devuelve 200 pero la app está rota internamente).
- **No resuelve `${VAR}` con valores de entorno**. Si tu `image: ${MY_IMAGE}` no tiene tag literal en el YAML, no se reporta como latest — porque no se sabe.
- **No valida redes custom**. Salir del scope MVP — puede llegar en una versión futura.
- **Sigue `extends:` y `include:` solo a un nivel** (en compose v2.20+). Composes muy anidados pueden tener falsos negativos.

---

## Dependencias

| Dependencia | Cómo instalar | Requerida o opcional |
|---|---|---|
| `python>=3.11` | viene con el SO | requerida |
| `pyyaml` | `pip install pyyaml` | requerida |

Sin binarios externos. No invoca `docker` ni `docker compose`.

---

## Ejemplos de salida

### Caso con hallazgos

```text
docker-compose-doctor — repo: /ruta/a/mi-proyecto
  archivo: compose.yml (5 servicios)

[errors]
  ✗ Puerto host 8080 duplicado entre servicios 'api' y 'admin'
    api:    "8080:8000"  (línea 14)
    admin:  "8080:80"    (línea 41)
  ✗ env_file inexistente en servicio 'worker': ./envs/worker.env (línea 67)

[warnings]
  ⚠ Servicio 'api' sin healthcheck — depends_on no podrá esperar a service_healthy
  ⚠ Servicio 'worker' depende de 'db' (que tiene healthcheck) con depends_on simple
    Sugerencia:
        depends_on:
          db:
            condition: service_healthy
  ⚠ Imagen 'redis' sin tag (línea 52) — pinnea a 'redis:7.2-alpine' o similar
  ⚠ Volumen 'old_cache' declarado pero no referenciado por ningún servicio

Resumen: 2 errores, 4 warnings.
```

Exit `1` (errores presentes).

### Caso limpio

```text
docker-compose-doctor — repo: /ruta/a/mi-proyecto
  archivo: compose.yml (5 servicios)

✓ Puertos: sin conflictos
✓ Healthchecks: 5/5 servicios cubiertos
✓ depends_on: todas las dependencias usan condition apropiada
✓ Imágenes: todas pinneadas
✓ Volúmenes: sin huérfanos
✓ env_file: todos los archivos existen

Resumen: 0 errores, 0 warnings. OK para `docker compose up`.
```

Exit `0`.

---

## Integración con flujo de trabajo

Combinable con [[yaml-control]] (valida sintaxis YAML del compose) y [[pre-push-guard]] (orquesta ambos + tests antes de pushear).

```bash
# Antes de un cambio importante al stack
python ~/.claude/skills/yaml-control/yaml_control.py
python ~/.claude/skills/docker-compose-doctor/docker_compose_doctor.py
docker compose up -d
```
