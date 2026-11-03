---
name: nombre-del-skill
description: Una frase clara que describa qué hace el skill + cuándo invocarlo. Incluir triggers en español y/o inglés. Ejemplo "Audita seguridad del repo cruzando deps contra OSV.dev. Úsalo cuando el usuario diga 'audita seguridad', 'scan CVE' o similar."
metadata:
  capabilities: []
disallowed-tools:
  - WebFetch
  - WebSearch
---

# nombre-del-skill

Descripción extendida del skill. Qué problema resuelve. Por qué existe.

---

## Alcance y permisos

| | |
|---|---|
| **Capacidades del script** | ninguna — es un skill de criterio, sin script ejecutable |
| **Qué toca** | Nada — es la plantilla desde la que se copia un skill nuevo. |
| **Qué nunca toca** | No se instala ni se invoca; `main.py` es un esqueleto. |
| **Herramientas retiradas** | `WebFetch`, `WebSearch` |

**No declara `allowed-tools`**, y es deliberado: ese campo *preaprueba* herramientas —se salta la confirmación durante el turno que invoca el skill— en vez de limitarlas. Declararlo aquí no acotaría nada: quitaría la confirmación del usuario. `disallowed-tools` sí retira herramientas del pool mientras el skill está activo, y ahí es donde se acota de verdad.

Un skill nuevo arranca sin preaprobar nada y con las herramientas de red retiradas: si las necesita, se añaden a conciencia al quitarlas de aquí.

---

## Cuándo invocar este skill

Triggers explícitos:

- "frase en español 1"
- "frase en español 2"
- "english phrase 1"

Triggers proactivos (cuándo el agente debería usarlo sin que se lo pidan):

- Después de X
- Antes de Y

---

## Cómo se invoca

```bash
python ~/.claude/skills/nombre-del-skill/main.py [args]
```

Modos:

```bash
python .../main.py                # default
python .../main.py --flag         # variante
```

---

## Qué hace exactamente

1. Paso 1
2. Paso 2
3. ...

---

## Qué NO hace / limitaciones

- Limitación 1
- Limitación 2

---

## Dependencias

| Dependencia | Cómo instalar | Requerida o opcional |
|---|---|---|
| `python>=3.11` | viene con el SO | requerida |
| `bandit` | `pip install bandit` | opcional (capa SAST) |

---

## Ejemplos de salida

```text
ejemplo de output
```
