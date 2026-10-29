---
name: release-evidence-auditor
description: >-
  Audita la evidencia técnica de un release — versión, gates, CI, artefactos,
  empaquetado, publicación y coherencia documental — clasificando cada
  afirmación en un solo nivel (ejecución local fresca · resultado remoto
  comprobado · inspección de artefacto · inspección estática · no comprobada).
  Un workflow iniciado no es un workflow verde y un build aprobado no prueba la
  instalación: entrega una matriz afirmación→fuente→evidencia→resultado con
  severidades y riesgo residual. Úsalo cuando el usuario diga "verifica el
  release", "¿está listo para publicar?", "revisa el artefacto y los
  checksums", "cuadra la versión con el changelog", "audit the release",
  "release readiness", "verify the build artifact". No certifica usabilidad ni
  producción, y auditar no autoriza publicar.
---

# Auditor de evidencia de release

## Objetivo

Determina si las afirmaciones de entrega están respaldadas por evidencia fresca y trazable. Separa claramente compilación, empaquetado, CI, publicación y comportamiento funcional. Este skill complementa las pruebas de producto: un artefacto correcto puede seguir teniendo fallos para usuarios finales.

## Reglas de evidencia

Clasifica cada afirmación en una sola categoría primaria:

1. **Ejecución local fresca:** comando ejecutado en el commit y entorno informados.
2. **Resultado remoto comprobado:** estado final consultado directamente en CI, tienda, registro o despliegue.
3. **Inspección de artefacto:** contenido, metadatos, firma, versión o permisos observados en el paquete generado.
4. **Inspección estática:** configuración o documentación revisada sin ejecutar el comportamiento.
5. **No comprobada:** falta acceso, entorno, artefacto o autorización; indica la causa y el riesgo.

No uses un workflow iniciado como evidencia de éxito. No uses un build aprobado como prueba de instalación, apertura o usabilidad. Una afirmación histórica fechada no se actualiza como si fuera el estado actual.

## Flujo de trabajo

1. Lee las instrucciones del repositorio, identifica cambios ajenos y registra commit, rama, estado del árbol y entorno.
2. Localiza las fuentes canónicas de versión, dependencias, plataforma soportada, configuración de build y publicación.
3. Contrasta marcadores de estado actual entre manifests, lockfiles, código, documentación, metadatos de paquete y páginas de distribución. Conserva referencias históricas de changelog y releases anteriores.
4. Ejecuta de nuevo los gates aplicables con el gestor y comandos definidos por el proyecto. Registra comando, salida, código de retorno y duración cuando sea útil. No reutilices caché como sustituto de una ejecución fresca sin declararlo.
5. Genera el artefacto cuando el alcance lo autorice. Inspecciona formato, tamaño, versión, identificador, arquitectura, permisos/capabilities, archivos incluidos, mapas o símbolos y firma cuando sean aplicables.
6. Si existe CI o publicación remota y está dentro del alcance, consulta el estado final real y vincula ejecución, commit y artefacto. Usa `N/A` cuando no exista servicio remoto.
7. Revisa que instalación, actualización, migración, rollback y distribución tengan instrucciones comprobables; marca como no ejecutado lo que requiera un dispositivo, cuenta o permiso ausente.
8. Reconcilia documentación sólo si el usuario autorizó cambios. Distingue siempre estado actual de referencias históricas.
9. Entrega una matriz afirmación→fuente→evidencia→resultado, incidencias por severidad y riesgos residuales.

## Severidad

- **Bloqueante:** artefacto inexistente/inservible, versión equivocada, firma inválida, gate crítico fallido o publicación asociada al commit incorrecto.
- **Alta:** evidencia incompleta que puede entregar un producto erróneo, incompatible o no actualizable.
- **Media:** incoherencia o carencia con alternativa manual verificable.
- **Baja:** defecto de presentación o trazabilidad sin impacto directo en el artefacto.

## Veredicto

- **Evidencia de release suficiente:** los gates y artefactos críticos del alcance están ligados al commit y pasaron.
- **No preparar release:** existe al menos un fallo bloqueante o alto sin mitigación comprobada.
- **Bloqueado por acceso/entorno:** no se puede comprobar ninguna evidencia crítica por falta de recurso concreto.

Emite el veredicto por plataforma o artefacto y después un resumen global. Un artefacto crítico fallido fuerza **No preparar release**. El veredicto no significa “funcional”, “usable”, “seguro” ni “listo para producción”; esas conclusiones requieren pruebas específicas.

## Límites de autorización

Auditar no autoriza publicar paquetes, crear releases, subir commits, modificar secretos, firmar con credenciales reales, desplegar ni promover entornos. Hazlo sólo por petición o aprobación explícita. No descargues ni ejecutes artefactos no confiables fuera de un entorno aislado.

## Informe mínimo

Usa [references/release-evidence-template.md](references/release-evidence-template.md). Incluye evidencia negativa y pruebas no ejecutadas; no ocultes fallos detrás de un resumen verde.
