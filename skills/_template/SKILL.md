---
name: nombre-del-skill
description: Una frase clara que describa qué hace el skill + cuándo invocarlo. Incluir triggers en español y/o inglés. Ejemplo "Audita seguridad del repo cruzando deps contra OSV.dev. Úsalo cuando el usuario diga 'audita seguridad', 'scan CVE' o similar."
---

# nombre-del-skill

Descripción extendida del skill. Qué problema resuelve. Por qué existe.

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

```
ejemplo de output
```
