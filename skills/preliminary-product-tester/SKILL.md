---
name: preliminary-product-tester
description: >-
  Preflight genérico de producto — diagnóstico temprano con evidencia
  clasificada en cinco niveles (funcional interactiva · automatizada ·
  build/integración · inspección estática · no ejecutada) que nunca asciende un
  build verde a flujo probado. Cubre Web, móvil, escritorio, API y servicios:
  enumera capacidades, corre los gates existentes como línea base, recorre
  primera apertura, tarea principal, persistencia, errores y límites, y emite
  veredicto por superficie (continuar · corregir antes de ampliar · escalar a
  especialista · bloqueado por entorno) sin promediar resultados. Úsalo cuando
  el usuario diga "revisa la calidad de esto", "QA temprano", "qué le falta
  antes de publicar", "pruébalo antes de entregarlo", "early QA", "preliminary
  testing", "smoke test del producto". No sustituye una certificación formal,
  un pentest ni una auditoría de accesibilidad especializada.
---

# preliminary-product-tester — preflight de producto

## Objetivo

Produce un diagnóstico temprano, genérico y accionable desde la perspectiva del usuario. Detecta fallos antes de una validación formal, prioriza riesgos y recomienda la siguiente capa de pruebas. Corrige problemas solo cuando el encargo autoriza cambios y deja evidencia reproducible. Trata documentación, tests existentes y afirmaciones del producto como hipótesis hasta contrastarlas.

El resultado es un **preflight de producto**, no una certificación. Debe permitir decidir si conviene seguir desarrollando, corregir primero, pasar a QA especializado o preparar una prueba de release.

## Clasificación obligatoria de evidencia

Etiqueta cada conclusión con uno de estos niveles y no los mezcles:

1. **Funcional interactiva:** el flujo se ejecutó mediante la interfaz o API pública y se observó el resultado final.
2. **Automatizada:** una prueba ejecutó el comportamiento y pasó con una aserción significativa.
3. **Build/integración:** compiló, empaquetó o sincronizó; esto no demuestra que el flujo sea usable.
4. **Inspección estática:** código o configuración parecen soportarlo; nunca lo presentes como funcionamiento comprobado.
5. **No ejecutada:** faltó dispositivo, cuenta, servicio, dato, permiso o entorno. Explica exactamente qué falta.

Nunca conviertas 3 o 4 en 1. “No falló” tampoco equivale a “funciona”. Si una prueba automatizada recorre una API o UI pública, usa **Automatizada** como nivel primario y anota la superficie pública como contexto; reserva **Funcional interactiva** para un recorrido realmente operado y observado mediante la interfaz/API.

## Flujo de trabajo

1. Lee instrucciones del repositorio y conserva cambios ajenos. Identifica superficies, usuarios, plataformas, instalación, datos persistentes e integraciones.
2. Reúne una línea base ejecutando los gates existentes. Registra comando, entorno, resultado y artefacto; no resumas un fallo como aprobado.
3. Enumera entre tres y siete capacidades principales según impacto/riesgo y construye una matriz preliminar de recorridos reales: primera apertura, tarea principal, navegación, persistencia, errores recuperables, reanudación, permisos, accesibilidad básica y límites de recursos. Cruza cada flujo sensible al volumen con cardinalidad mínima (vacío o un elemento), típica y muy grande; separa cantidad de elementos de tamaño en bytes. Lee [references/validation-playbook.md](references/validation-playbook.md) para elegir las filas aplicables y [references/specialist-routing.md](references/specialist-routing.md) para derivar pruebas profundas.
4. Prioriza límites donde suelen escapar fallos: UI↔estado, aplicación↔sistema operativo, foreground↔background, archivo válido↔corrupto, red↔offline, sesión nueva↔restaurada y operación lenta↔acciones repetidas.
5. Usa archivos y datos de prueba controlados. Los mocks ayudan al diagnóstico, pero no sustituyen el recorrido de aceptación cuando la superficie real está disponible.
6. Reproduce cada defecto antes de corregirlo. Conserva la observación concreta, identifica la causa y repite el mismo flujo después del cambio.
7. Añade una regresión automatizada cuando pueda representar el fallo de forma significativa. Evita pruebas que solo busquen texto salvo que ese texto sea el contrato real que se protege.
8. Si el usuario pidió mejorar o corregir, implementa cambios acotados y vuelve a ejecutar gates y recorridos afectados. Si pidió solo auditar, no modifiques el producto.
9. Reconcilia documentación actual, changelog y conteos con la evidencia. Conserva intactas las referencias históricas fechadas. No inventes versión, release, publicación ni aprobación remota.
10. Entrega un informe con: alcance, entorno, evidencia ejecutada, defectos y correcciones, regresiones, artefactos, resultados remotos (o `N/A` con motivo), pruebas no ejecutadas y siguiente nivel recomendado.

## Veredicto preliminar

Usa estados discretos, no porcentajes inventados:

- **Continuar:** los recorridos preliminares críticos pasaron y los riesgos pendientes están acotados.
- **Corregir antes de ampliar pruebas:** existe al menos un fallo reproducible que bloquea o degrada la tarea principal.
- **Escalar a especialista:** seguridad, accesibilidad, rendimiento, cumplimiento, hardware o plataforma requieren herramientas/conocimiento específico.
- **Bloqueado por entorno:** no existe la superficie necesaria para obtener evidencia útil.

Emite un veredicto por superficie (por ejemplo Web, API, Android, escritorio) y luego un resumen global sin promediar resultados. Una superficie crítica fallida fuerza **Corregir antes de ampliar pruebas**; usa **Bloqueado por entorno** global solo si ninguna superficie principal obtuvo evidencia útil. El veredicto aplica solo al alcance ejecutado.

Clasifica cada hallazgo:

- **Bloqueante:** impide la tarea principal, causa pérdida de datos o deja el producto inutilizable.
- **Alta:** degrada fuertemente un recorrido principal sin alternativa razonable.
- **Media:** afecta un recorrido secundario o tiene alternativa aceptable.
- **Baja:** defecto menor sin impacto funcional relevante.

Incluye impacto para el usuario, evidencia y siguiente acción por cada hallazgo.

## Criterios de calidad

- Prueba al menos un flujo feliz y uno degradado o erróneo por cada capacidad principal seleccionada; si el alcance no lo permite, registra el caso como fuera de alcance o no ejecutado.
- En navegación y edición, exige un oráculo de coherencia: una acción produce una sola transición y el valor visible, el contenido mostrado, el estado persistido y la acción siguiente concuerdan. Repite límites e interacciones rápidas para descubrir saltos, dobles efectos y estado obsoleto.
- Comprueba que el producto se recupera sin perder el trabajo anterior cuando una operación nueva falla.
- Ejercita acciones consecutivas o concurrentes en controles sensibles a carreras.
- Valida responsive/táctil con el viewport adecuado, pero llama “simulación de viewport” a lo que no ocurrió en hardware. Un gesto sintético tampoco acredita sensor, latencia ni interacción física real.
- Genera fixtures reproducibles y no sensibles para cardinalidad mínima, típica y extrema. Verifica además que paneles cerrados no disparen trabajo proporcional al total y que cerrar o sustituir el recurso cancele tareas diferidas.
- En móvil o escritorio, separa compilación nativa de instalación, ciclo de vida, intents/asociaciones, gestos, permisos y compartir.
- Si hay persistencia, verifica guardar, cerrar/reabrir, límite/cuota, borrar y aislamiento del original.
- Si existe CI, consulta el resultado real después de subir; “workflow iniciado” no significa “verde”.

## Límites de autorización

La auditoría no autoriza por sí sola publicar, subir commits, crear releases, instalar software, cambiar infraestructura ni usar datos sensibles. Realiza esas acciones solo cuando el usuario las haya pedido o aprobado según corresponda.

No ejecutes pruebas activas contra producción, tenants ajenos, cuentas reales, endpoints remotos con coste, carga significativa o datos de terceros sin autorización específica para ese destino y alcance. Prefiere entornos locales o de prueba. La mera existencia de una URL o credencial no concede permiso.

## Condición de cierre

No declares “validación completa”, “certificado” ni “listo para producción” desde este skill preliminar. Usa una formulación precisa: qué quedó probado, en qué entorno, qué bloquea al usuario y qué riesgo residual debe cubrir el siguiente nivel. Una evaluación temprana honesta con huecos explícitos es mejor que cobertura ficticia.
