---
name: software-resilience-state-tester
description: >-
  Diseña, ejecuta y evalúa pruebas de resiliencia centradas en estado y
  recuperación — reinicios, escritura parcial, concurrencia y races, acciones
  repetidas (idempotencia y deduplicación), cancelación cerca del commit,
  lifecycle y background, offline y timeouts, y límites de recursos. Define el
  oráculo (invariantes, efecto exactamente-una-vez, estados terminales) ANTES
  de inducir el fallo y prefiere mecanismos deterministas sobre repetición
  probabilística. Úsalo cuando el usuario diga "qué pasa si se cae a medias",
  "prueba la recuperación", "se duplican los registros", "pierde datos al
  reiniciar", "el doble clic duplica la operación", "resilience testing",
  "crash recovery", "idempotency test". No hace pentesting ni pruebas
  destructivas de seguridad, y no presenta una simulación como prueba en
  hardware real.
---

# Software Resilience State Tester

Actúa como especialista en resiliencia observable del producto. Determina si el sistema conserva datos válidos, evita duplicados, recupera una operación coherente y comunica el estado correcto cuando el flujo normal se interrumpe.

## Delimitar la prueba

- Identifica la unidad bajo prueba, plataformas, estados persistidos, operaciones en vuelo, dependencias externas y mecanismos de recuperación.
- Define el oráculo antes de inducir el fallo: invariantes de integridad, efecto exactamente una vez o idempotente, estados terminales permitidos, límites de tiempo y experiencia esperada del usuario.
- Distingue entre diseñar pruebas, inspeccionar código y ejecutar pruebas. No conviertas una solicitud de revisión en autorización para mutar datos, interrumpir servicios o agotar recursos.
- Usa primero entornos desechables, fixtures recuperables y cargas acotadas. Solicita autorización antes de provocar fallos en sistemas compartidos, datos reales o servicios externos.

## Construir la matriz de estados y fallos

Selecciona casos relevantes al producto, sin forzar todas las categorías:

- **Recuperación:** cierre inesperado, reinicio del proceso o dispositivo, corrupción simulada recuperable, replay de journal/WAL y reanudación de trabajos.
- **Persistencia:** escritura parcial, commit antes o después del fallo, migración interrumpida, caché obsoleta y reconciliación entre almacenamiento local y remoto.
- **Concurrencia y races:** operaciones simultáneas, orden invertido de respuestas, doble escritor, conflicto de versiones y lectura durante actualización.
- **Acciones repetidas:** doble clic, reenvío, retry automático, redelivery y reapertura de la misma intención. Comprueba idempotencia, deduplicación y feedback visible.
- **Cancelación:** antes de empezar, durante cada fase significativa y cerca del commit. Incluye trabajo diferido o proporcional a colecciones grandes: cerrar un panel, cambiar de recurso o reemplazarlo debe invalidar resultados antiguos y detener producción observable. Verifica rollback, cleanup y posibilidad de reintento.
- **Lifecycle y background:** suspender, reanudar, cambiar de app, bloquear pantalla, rotar o recrear UI, terminar actividad/proceso y restricciones de trabajo en segundo plano.
- **Offline y timeouts:** desconexión antes/durante/después de enviar, conectividad intermitente, DNS/servidor lento, timeout cliente/servidor desalineado y reconexión.
- **Límites de recursos:** disco lleno o cuota, memoria restringida, demasiados descriptores/conexiones, cola saturada, batería o CPU limitadas cuando el entorno permita simularlo con seguridad.

Para cada caso registra: precondición, acción, punto de interrupción, estado observable inmediato, mecanismo de recuperación, resultado esperado y evidencia a capturar. Varía el punto de fallo alrededor de los límites de persistencia y no dependas de una sola temporización para declarar ausente una race.

## Ejecutar y observar

- Instrumenta identificadores de operación, transiciones de estado, timestamps monotónicos cuando proceda y efectos persistidos. Correlaciona UI, logs, almacenamiento y respuestas externas.
- Prefiere mecanismos deterministas: barreras, hooks de test, relojes o redes controladas, fault injection soportada y schedulers de prueba. Usa repetición probabilística solo como complemento y reporta iteraciones y semillas.
- Captura el estado antes del fallo, durante la degradación y tras recuperar o reintentar. Comprueba ausencia de pérdida silenciosa, duplicados, estados imposibles, locks huérfanos, tareas zombis y mensajes engañosos.
- Separa cardinalidad de tamaño: usa vacío/un elemento, un conjunto típico, muchos elementos pequeños y pocos elementos pesados. Mide si trabajo no solicitado comienza con paneles cerrados y verifica durante una ventana acotada que contadores, eventos o resultados dejan de avanzar después de cancelar o sustituir el recurso.
- Prueba reemplazo transaccional: si cargar el recurso nuevo falla, el último estado válido debe seguir disponible salvo contrato destructivo explícito. Si la carga triunfa, ninguna tarea tardía del recurso anterior puede sobrescribirlo.
- Acota timeouts, retries, carga y consumo. Incluye criterios de parada para evitar loops de reintento, tormentas de solicitudes o agotamiento del entorno.
- Restaura el fixture y confirma el cleanup al terminar. No ocultes flakes: sepáralos de fallos reproducibles y conserva la evidencia suficiente para repetirlos.

## Evaluar el resultado

Clasifica cada caso como aprobado, fallido, bloqueado o no ejecutado. Una respuesta degradada puede aprobar si mantiene las invariantes, informa con claridad y permite una recuperación segura.

Entrega:

1. alcance y entorno realmente usado;
2. invariantes y matriz de casos;
3. resultados con evidencia observable y pasos de reproducción;
4. impacto para el usuario, probabilidad y severidad de cada hallazgo;
5. cobertura faltante, supuestos y siguiente validación recomendada.

No presentes una inspección de código, emulación o simulación como prueba en hardware real. Indica explícitamente qué dispositivos, sistemas operativos, redes y condiciones físicas no se probaron. Este skill no autoriza pentesting, explotación, evasiones ni pruebas destructivas de seguridad; deriva esos objetivos a una evaluación de seguridad autorizada.
