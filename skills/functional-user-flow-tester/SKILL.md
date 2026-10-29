---
name: functional-user-flow-tester
description: >-
  Ejecuta pruebas funcionales black-box de flujos de usuario en productos Web,
  móviles, de escritorio y APIs públicas — ruta feliz, ruta degradada,
  recuperación, accesibilidad básica y matriz de cardinalidad (vacío · típico ·
  muy grande) separando cantidad de elementos de tamaño en bytes. Cada
  conclusión se apoya en evidencia observable por el usuario, nunca en logs
  internos ni en el código fuente, y lo que no se pudo ejecutar sale como NO
  EJECUTADO con el motivo. Úsalo cuando el usuario diga "prueba este flujo",
  "valida la app como un usuario", "revisa la navegación o el formulario", "haz
  QA funcional", "test the user flow", "black-box testing", o entregue una URL,
  un binario o una API para recorrer. No hace pentesting, pruebas de carga,
  resiliencia interna avanzada ni certificación formal de accesibilidad.
---

# Functional User Flow Tester

Evalúa el producto como lo haría un usuario o consumidor externo. Basa las conclusiones en resultados observables y separa claramente hechos, inferencias y restricciones del entorno.

## Acordar el alcance operativo

- Identifica superficie, entorno, roles disponibles, flujos prioritarios y criterio de éxito a partir de la solicitud y de la documentación entregada.
- Si faltan detalles menores, adopta supuestos conservadores y decláralos. Pregunta solo cuando una elección cambie materialmente el alcance, los datos o el riesgo.
- Trata las credenciales, cuentas, datos y permisos disponibles como límites estrictos. No crees cuentas, compres, publiques, envíes mensajes ni alteres datos reales sin autorización implícita en el flujo solicitado o confirmación explícita.
- Para APIs, prueba únicamente endpoints públicos o documentados con los métodos y scopes autorizados. No busques endpoints ocultos ni intentes evadir controles.

## Diseñar la cobertura

Deriva casos a partir de objetivos de usuario, no de la implementación interna. Prioriza cada flujo crítico con una cobertura proporcional:

1. **Ruta feliz:** entrada válida, transición esperada y resultado final verificable.
2. **Ruta degradada:** al menos una condición realista como datos inválidos o incompletos, permiso denegado, recurso ausente, sesión vencida o fallo de red seguro de simular.
3. **Recuperación:** corrección de entrada, reintento, volver atrás, recarga o reanudación sin pérdida o duplicación inesperada.
4. **Accesibilidad básica:** navegación por teclado o equivalente, foco visible y lógico, nombre/rol accesible de controles, mensajes de error comprensibles, zoom/reflow cuando aplique y contraste evidente. Registra estas comprobaciones como preliminares, no como auditoría WCAG.

Incluye límites y transiciones relevantes: estado inicial y persistido, navegación, validaciones, permisos, cancelación, duplicación de acciones y consistencia del resultado. Evita combinaciones exhaustivas que no cambien el riesgo funcional.

### Matriz obligatoria para navegación y contenido variable

- Usa fixtures reproducibles y sin datos privados con cardinalidad mínima (vacío si es válido y exactamente un elemento), típica y muy grande. Prueba tamaño en bytes como un eje distinto: muchos elementos pequeños y pocos elementos pesados ejercitan riesgos diferentes.
- Define el oráculo de cada transición antes de ejecutarla: una acción debe producir una sola transición; control visible, contenido renderizado, estado restaurable y efecto de la acción siguiente deben señalar el mismo destino.
- Prueba controles, teclado, entrada directa con confirmación y pérdida de foco, repetición rápida y límites anterior/siguiente. En los límites, repetir la acción debe ser idempotente salvo contrato explícito.
- Para gestos, registra estado al inicio, durante y al final. Distingue pan de contenido ampliado frente a navegación. Alcanzar un borde durante el gesto no cuenta como una nueva intención ni debe disparar una transición de límite accidental.
- Abre paneles o vistas costosas solo cuando el usuario lo hace y observa si el trabajo crece con la cardinalidad. Cierra, cambia o sustituye el recurso y verifica durante una ventana acotada que el trabajo anterior deje de producir resultados visibles.
- Si falla una segunda apertura o sustitución, verifica que el recurso válido anterior siga utilizable, salvo que el contrato establezca un reemplazo destructivo explícito.

## Ejecutar como black-box

- Usa la interfaz pública apropiada: navegador, emulador o dispositivo disponible, aplicación de escritorio, o cliente HTTP para una API pública.
- Observa lo que el usuario puede percibir: contenido, estado, respuesta, código HTTP, tiempo aproximado, navegación, persistencia y mensajes. No uses logs internos, base de datos ni código fuente como sustituto del resultado observable; si se consultan para orientar la prueba, etiqueta esa información por separado.
- Captura evidencia suficiente para reproducir y sostener cada conclusión: pasos, datos de prueba sanitizados, entorno, marcas de tiempo cuando aporten valor, capturas, salida de consola relevante o pares petición/respuesta sin secretos.
- Ante un defecto, conserva la reproducción previa, repite exactamente el recorrido después del cambio y añade una regresión automatizada significativa cuando sea posible. Una prueba nueva que nunca falla contra la versión defectuosa no demuestra que proteja el arreglo.
- Minimiza efectos laterales. Usa datos desechables y limpia solo los artefactos creados durante la prueba cuando sea seguro y esté autorizado.
- Si una plataforma, dispositivo, cuenta o capacidad no está disponible, no simules evidencia. Marca el caso como no ejecutado y explica qué falta. Un viewport móvil o gesto sintético es evidencia automatizada/simulada, no prueba táctil en hardware.

## Evaluar y comunicar

Para cada caso informa: identificador breve, objetivo, precondiciones, pasos, resultado esperado, resultado observado, estado (`pasa`, `falla`, `bloqueado` o `no ejecutado`) y evidencia. Distingue una falla del producto de una limitación del entorno.

Documenta cada hallazgo con:

- flujo y plataforma afectados;
- pasos mínimos reproducibles y datos no sensibles;
- comportamiento esperado frente al observado;
- evidencia vinculada o localizada;
- impacto para el usuario, frecuencia observada y severidad razonada;
- recuperación o workaround comprobado, si existe.

Cierra con un resumen de cobertura, riesgos principales, casos bloqueados y siguiente validación recomendada. No afirmes cobertura total, conformidad de accesibilidad, seguridad o robustez si esas propiedades no fueron evaluadas por una práctica especializada.

## Límites

Este skill no realiza análisis profundo de compilación, dependencias, CI/CD o arquitectura; pentesting, fuzzing ofensivo, explotación o evasión de autenticación; pruebas de carga, caos, failover o resiliencia interna avanzada; certificación formal de accesibilidad; ni pruebas físicas no disponibles. Puede señalar cuándo un síntoma funcional justifica derivar a esas disciplinas, sin ampliar el alcance por cuenta propia.
