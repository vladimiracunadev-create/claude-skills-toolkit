# Enrutamiento a skills especializados

El skill preliminar mantiene la visión global y deriva profundidad sin inflar sus propias conclusiones.

| Necesidad | Skill complementario | Resultado esperado |
|---|---|---|
| Tareas de usuario, navegación, entradas, errores visibles y compatibilidad básica | `functional-user-flow-tester` | recorridos black-box reproducibles por superficie |
| Persistencia, reanudación, cancelación, concurrencia, offline y ciclo de vida | `software-resilience-state-tester` | transiciones y recuperación con invariantes comprobadas |
| Versiones, gates, CI, paquetes, firmas, publicación y documentación de entrega | `release-evidence-auditor` | trazabilidad de commit a artefacto y estado remoto |
| Seguridad ofensiva, accesibilidad formal, carga/rendimiento, cumplimiento o hardware especializado | especialista externo apropiado | evaluación especializada; no debe simularse desde el preflight |

Los skills complementarios pueden encadenarse (o delegarse a subagentes) sólo cuando sus superficies y recursos sean independientes. El preflight agrega los resultados por superficie: no promedia, no convierte “build verde” en funcionalidad y conserva cada caso no ejecutado.
