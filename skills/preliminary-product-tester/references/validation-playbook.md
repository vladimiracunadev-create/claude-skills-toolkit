# Playbook preliminar de validación

Usa esta referencia para construir un preflight proporcionado al producto y preparar el traspaso a QA profundo. Selecciona solo las filas aplicables; no simules superficies ausentes ni conviertas esta matriz en una certificación.

## Matriz base

| Área | Recorridos mínimos | Evidencia útil |
|---|---|---|
| Instalación/arranque | instalación limpia, actualización, primera apertura, reapertura | versión instalada, pantalla inicial, logs sin error fatal |
| Tarea principal | caso pequeño, caso realista, caso límite | resultado visible o respuesta pública, datos usados |
| Navegación | controles principales, Atrás, deep link/intento, restauración | destino y estado conservado |
| Persistencia | guardar, cerrar, reabrir, borrar, cuota agotada | dato recuperado, eliminación confirmada, degradación segura |
| Errores | entrada inválida, operación cancelada, recurso ausente | mensaje accionable y estado anterior intacto |
| Rendimiento percibido | recurso grande, acciones rápidas, operación prolongada | interfaz responsiva, cancelación o progreso coherente |
| Accesibilidad | nombres accesibles, foco, teclado, contraste básico | árbol accesible y navegación observada |
| Privacidad/permisos | solicitud real, datos almacenados, compartir | permiso exacto y contenido transmitido |
| Compatibilidad | viewport, SO/runtime soportado, orientación | entorno exacto y comportamiento observado |
| SaaS/roles | rol mínimo, rol elevado, separación entre tenants y expiración de sesión | cuenta/tenant de prueba y resultado visible |

## Matriz de cardinalidad y coherencia

Para colecciones, páginas, resultados, archivos o registros, ejecuta como mínimo:

| Clase | Fixture | Riesgo buscado |
|---|---|---|
| Mínima | vacío cuando sea válido y exactamente un elemento | límites, controles deshabilitados e idempotencia |
| Típica | varios elementos representativos | navegación y persistencia ordinarias |
| Alta cardinalidad | muchos elementos generados sin datos privados | trabajo O(N), memoria, cancelación y estado obsoleto |
| Gran tamaño | pocos elementos pesados, separado de la cardinalidad | tiempo de lectura/render, progreso y recursos |

En cada transición comprueba cuatro observables: control o valor visible, contenido realmente mostrado, estado conservado y efecto de la acción siguiente. Una sola entrada, confirmación o gesto debe causar una sola transición salvo que el contrato documentado indique otra cosa. En gestos, diferencia inicio, desplazamiento y final; llegar al borde durante el gesto no debe activar una acción de límite por sí solo.

## Extensiones por superficie

### Web

- carga directa y recarga de rutas;
- viewport estrecho y ancho;
- teclado, foco y paneles superpuestos;
- almacenamiento nuevo y restaurado;
- consola y solicitudes de red durante el flujo.
- navegador principal y, si el riesgo lo justifica, un segundo motor; ausencia de navegador adicional se registra como no ejecutada.

### Android/iOS

- APK/AAB/IPA compilado no equivale a instalación probada;
- selector de archivos, intents/deep links y app ya activa;
- Atrás, rotación, background/restore y muerte del proceso;
- gestos de hardware, teclado virtual, safe areas y hoja de compartir;
- versión mínima y una versión moderna cuando existan dispositivos.

### Escritorio

- instalador y portable si ambos existen;
- asociación de archivos, argumentos de arranque y segunda instancia;
- rutas con espacios, archivos ausentes y permisos limitados;
- minimizar/restaurar, cierre y persistencia.

### API/servicio

- autenticación válida, inválida y expirada;
- idempotencia, reintentos, timeouts y concurrencia;
- validación de esquema y errores sin información sensible;
- persistencia real o entorno de prueba representativo.

## Plantilla de informe

```markdown
# Validación funcional · FECHA

## Alcance y entorno
- producto/versión/commit
- plataformas realmente disponibles
- datos o fixtures empleados

## Evidencia ejecutada
| Superficie | Nivel | Flujo/comando | Resultado observado | Artefacto |
|---|---|---|---|---|

## Defectos comprobados y correcciones
| Severidad | Defecto reproducido | Causa | Cambio | Repetición posterior |
|---|---|---|---|---|

## Regresiones automatizadas
- prueba y comportamiento protegido

## No ejecutado
- escenario, causa concreta (recurso ausente, fuera de alcance o no priorizado) y riesgo residual

## Veredicto
- veredicto por superficie
- resumen global: continuar / corregir antes de ampliar / escalar a especialista / bloqueado por entorno
- siguiente nivel de prueba recomendado
```

Evita porcentajes de cobertura funcional salvo que exista una matriz cerrada con denominador explícito. No uses “completo”, “exhaustivo” o “listo para producción” sin definir y cumplir criterios de aceptación verificables.
