# Plantilla de evidencia de release

```markdown
# Auditoría de evidencia de release · FECHA

## Identidad
- repositorio, commit, rama y estado del árbol
- producto, versión y plataforma/artefacto
- entorno y herramientas

## Matriz de afirmaciones
| Plataforma/artefacto | Afirmación | Fuente canónica | Nivel de evidencia | Resultado | Referencia |
|---|---|---|---|---|---|

## Gates ejecutados
| Comando | Entorno | Resultado | Duración | Evidencia |
|---|---|---|---|---|

## Artefactos inspeccionados
| Artefacto | Procedencia/commit | Versión | Propiedades verificadas | Resultado |
|---|---|---|---|---|

## Resultados remotos
- ejecución final de CI/publicación, o N/A con motivo

## Incidencias
| Severidad | Hallazgo | Impacto | Evidencia | Acción siguiente |
|---|---|---|---|---|

## No comprobado y riesgo residual
- comprobación, causa concreta y riesgo

## Veredicto
- por plataforma/artefacto
- global: evidencia suficiente / no preparar release / bloqueado por acceso o entorno
```

Enlaza la ejecución o artefacto exacto, no sólo la portada del servicio. Si el hash, versión o commit no puede correlacionarse, decláralo como evidencia incompleta.
