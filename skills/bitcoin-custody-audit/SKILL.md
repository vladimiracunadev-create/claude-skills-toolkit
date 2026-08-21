---
name: bitcoin-custody-audit
description: >
  Audita la seguridad de una custodia Bitcoin en 14 etapas — procedencia de claves
  (fabricante, modelo y firmware con el que se creó cada semilla) cruzada contra la
  matriz de avisos publicados; frescura de esa matriz; arquitectura de custodia
  (single-sig, quorum N-de-N, monocultivo de fabricante); rechazo de material secreto
  en el código; secretos y ficheros prohibidos en el histórico de git; runtime
  empaquetado dentro del binario; superficie de dependencias; integridad de los enlaces
  del repositorio; postura del despliegue (bind, modo demo, puertos publicados);
  aislamiento del nodo Bitcoin Core (rpcallowip, rpcbind, credenciales); persistencia
  cifrada y fuerza de la clave de datos; workflows pinneados a SHA; verificación del
  artefacto publicado (checksums y firma); y proceso humano de respuesta. Declara
  SIEMPRE la cobertura real: una etapa que no pudo ejecutarse sale OMITIDA, nunca
  aprobada. Genera informe Markdown y plan de remediación deduplicado. NUNCA pide, lee
  ni acepta semillas, claves privadas ni passphrases. Úsalo cuando el usuario diga
  "audita mi custodia bitcoin", "revisa la seguridad de mis wallets", "¿me afecta el
  aviso de COLDCARD/Trezor?", "auditoría bitcoin", "revisa la procedencia de mis
  claves", "postura de seguridad del despliegue", "bitcoin custody audit", "wallet
  security review", o cuando cambie el inventario, la configuración o la matriz de
  avisos.
---

# bitcoin-custody-audit — auditoría de custodia Bitcoin en 14 etapas

Hermano de dominio de [`security-audit`](../security-audit/README.md) (12 capas).
Aquel audita **el repositorio**: dependencias, CVE, SAST, contenedor, secretos.
Este audita **la custodia**: de dónde vienen las claves, qué las puede romper y si
la instalación que las vigila está bien puesta.

No se solapan: se encadenan. En un repositorio de custodia conviene correr los dos,
y este declara explícitamente qué hereda de aquel.

## Las tres reglas que gobiernan el skill

1. **La cobertura se declara siempre.** Lo que no se pudo comprobar aparece como no
   comprobado. Un «0 hallazgos» sobre una superficie que no se miró es una mentira
   con formato de informe.
2. **Una etapa que no puede ejecutarse sale OMITIDA, no verde.** Sin inventario, sin
   git o sin configuración son motivos legítimos para omitir; ninguno lo es para
   aprobar.
3. **La ausencia de dato es un hallazgo.** No poder demostrar con qué firmware nació
   una clave **es** el problema, aunque la clave esté sana.

> [!IMPORTANT]
> Este skill **nunca** pide, lee ni acepta material secreto. No hay una sola ruta de
> código que consuma una semilla, una clave privada o una passphrase: el inventario
> son **metadatos** (fabricante, modelo, firmware, quorum), jamás claves. Si el skill
> encuentra material secreto en el repositorio, lo reporta como hallazgo — no lo usa.

---

## Las 14 etapas

### Bloque A — Las claves (1-3) · requieren inventario

| # | Etapa | Pregunta | Fallo típico |
|---|---|---|---|
| 1 | **Procedencia de claves y firmantes** | ¿Se puede demostrar con qué firmware y método nació cada semilla? | Inventario con `firmware_at_seed: unknown` que impide descartar cualquier aviso |
| 2 | **Frescura de la matriz de avisos** | ¿La inteligencia con la que se juzga está al día? | Panel en verde sobre avisos sin revisar en seis meses |
| 3 | **Arquitectura de custodia** | ¿La arquitectura contiene el compromiso de un firmante? | Alto valor en single-sig; multisig 3-de-3; tres dispositivos del mismo fabricante |

### Bloque B — El software (4-8) · sobre el repositorio

| # | Etapa | Pregunta | Fallo típico |
|---|---|---|---|
| 4 | **Rechazo de material secreto** | ¿Hay entradas que aceptarían una semilla sin guardia? | Un campo nuevo que nombra `mnemonic` en un fichero sin ninguna señal de rechazo |
| 5 | **Secretos en el histórico** | ¿Entró alguna vez material secreto al repositorio? | Un `.env` commiteado y «borrado» tres commits después |
| 6 | **Cadena de suministro del runtime** | ¿El motor que viaja dentro del binario está identificado y fijado? | `pkg` empaquetando un Node que nadie fijó ni revisó |
| 7 | **Superficie de dependencias** | ¿Cuánto código de terceros se ejecuta, y se puede auditar? | README que promete «cero dependencias» sobre un `package.json` con 12 |
| 8 | **Integridad del repositorio** | ¿Contiene lo que dice contener? | Documentación que remite a un runbook que ya no existe |

### Bloque C — La instalación (9-13) · sobre la configuración versionada

| # | Etapa | Pregunta | Fallo típico |
|---|---|---|---|
| 9 | **Postura de la instalación** | ¿Cómo está configurada? | `HOST=0.0.0.0` «para verlo desde el portátil» |
| 10 | **Aislamiento del nodo** | ¿El acceso al nodo es local y de solo lectura? | `rpcallowip=0.0.0.0/0` con usuario y contraseña estáticos |
| 11 | **Persistencia cifrada** | ¿El estado está cifrado y la clave es fuerte? | `DATA_KEY=clave123` en un `.env` versionado |
| 12 | **Automatización y CI** | ¿Los workflows están pinneados y con permisos mínimos? | `uses: action@v4` sobre una etiqueta que alguien puede mover |
| 13 | **Verificación del artefacto** | ¿Lo publicado se puede verificar antes de ejecutarlo? | Un release que publica el `.exe` sin checksums ni firma |

### Bloque D — Las personas (14)

| # | Etapa | Pregunta | Fallo típico |
|---|---|---|---|
| 14 | **Proceso humano de respuesta** | ¿Existe runbook y quién decide qué, antes de necesitarlo? | Descubrir durante el incidente que nadie definió quién aprueba mover fondos |

---

## Cómo se invoca

Desde la raíz del repositorio de custodia (trabaja sobre `Path.cwd()`):

```bash
# Las 14 etapas, informe por consola
python ~/.claude/skills/bitcoin-custody-audit/bitcoin_custody_audit.py

# Además, informe Markdown fechado en la raíz del repositorio
python ~/.claude/skills/bitcoin-custody-audit/bitcoin_custody_audit.py --report

# Solo algunas etapas (acepta rangos)
python ~/.claude/skills/bitcoin-custody-audit/bitcoin_custody_audit.py --stages 1,2,3,9-11

# Histórico completo en la etapa 5 (por defecto: últimos 2000 commits)
python ~/.claude/skills/bitcoin-custody-audit/bitcoin_custody_audit.py --deep

# Salida procesable · exit 1 también si alguna etapa quedó OMITIDA
python ~/.claude/skills/bitcoin-custody-audit/bitcoin_custody_audit.py --json --strict
```

| Flag | Efecto |
|---|---|
| `--inventory PATH` | Inventario explícito (por defecto busca `custody.json`, `bitcoin-custody.yml`, `.custody/inventory.*`) |
| `--stages LISTA` | `1,2,3` o `9-13`. Por defecto: las 14 |
| `--deep` | Etapa 5 sobre el histórico completo de git |
| `--report` | Escribe `SECURITY_AUDIT_BITCOIN_<fecha>.md` |
| `--out-dir DIR` | Directorio del informe |
| `--json` | Salida JSON con etapas, hallazgos y plan |
| `--strict` | Exit 1 también si alguna etapa quedó OMITIDA |

---

## El inventario de custodia

Las etapas 1-3 (y parte de la 6 y la 14) necesitan un inventario. Es **metadatos, no
claves**. JSON funciona sin dependencias; YAML requiere `pyyaml`.

```json
{
  "advisories_reviewed": "2026-08-01",
  "runtime_advisories_reviewed": "2026-08-01",
  "roles": {
    "aprueba_mover_fondos": "dos de los tres titulares, presencialmente",
    "custodia_firmante_c": "caja de seguridad bancaria"
  },
  "wallets": [
    {"id": "tesoreria", "quorum": "2-de-3", "value_tier": "high",
     "signers": ["cc-a", "tz-b", "led-c"]}
  ],
  "signers": [
    {"id": "cc-a", "vendor": "coldcard", "model": "Mk4",
     "firmware_at_seed": "5.1.2", "seed_created": "2024-03-11",
     "entropy_source": "device"}
  ],
  "advisories": [
    {"id": "CC-2023-01", "vendor": "coldcard", "models": ["Mk3"],
     "firmware_affected": "<4.1.0", "severity": "high",
     "url": "https://ejemplo.invalid/aviso"}
  ]
}
```

`firmware_affected` acepta `<4.1.0`, `>=1.2 <1.5`, `==2.0`, listas y `all`. Si el
firmware del firmante o el rango del aviso no permiten decidir, el cruce sale como
`W-PROV-INDECIDIBLE` — **nunca** como «no afectado».

---

## Qué produce

Una línea por etapa (`OK`, `!!` atención, `XX` fallo, `..` omitida) con su **cobertura**
y sus hallazgos; y, con `--report`, un `SECURITY_AUDIT_BITCOIN_<fecha>.md` con resumen,
tabla de etapas, hallazgos por etapa, **plan de remediación deduplicado** y una sección
final que enumera **lo que el informe no dice** (las etapas omitidas y por qué).

Códigos: los que empiezan por `F-` son fallos (exit 1); los `W-` describen deuda y no
tumban el proceso.

---

## Cuándo invocarlo

- Al cambiar el inventario: una wallet o un firmante nuevo cambia el mapa.
- Al publicar un aviso un fabricante que usas.
- Antes de cada release (etapas 4 a 8 y 13 son parte del checklist).
- Al cambiar la configuración del despliegue (etapas 9 a 11).
- Periódicamente, aunque no cambie nada: la etapa 2 detecta que **el mundo** cambió
  aunque tu repositorio no.

---

## Relación con `security-audit`

| Capa de `security-audit` | Aquí |
|---|---|
| `osv`, `kev`, `epss` | Etapa 6, adaptada: mira el runtime empaquetado y **no consulta la red** — delega la consulta de avisos en `security-audit` |
| `sast` | Etapa 4, acotada al dominio: entradas que aceptarían material secreto |
| `secrets` | Etapa 5, con patrones del dominio: `xprv`, WIF, descriptores privados y ficheros prohibidos |
| `workflows` | Etapa 12 |
| `container`, `typosquat` | No aplican a una custodia local |
| — | Etapas 1, 2, 3, 9, 10, 11, 13 y 14 son propias de este dominio |

Orden natural: primero `security-audit` sobre el repositorio, después
`bitcoin-custody-audit` sobre la custodia y la instalación. La etapa 7 se apoya en el
mismo razonamiento que [`python-deps-pinning`](../python-deps-pinning/README.md): sin
lockfile no hay versión que consultar.

---

## Limitaciones

- **No verifica la procedencia que le cuentas.** Si alguien registra un firmware
  incorrecto, el diagnóstico será incorrecto. Ningún programa puede comprobar qué
  firmware tenía un dispositivo hace dos años.
- **La matriz de avisos es manual y local.** El skill detecta que está vieja; no la
  actualiza, y **no accede a la red**.
- **La etapa 4 es estática.** Lee el código, no ejecuta la aplicación: la versión
  fuerte de esa comprobación se hace contra la app en marcha, antes del release.
- **La etapa 5 no confirma frases mnemónicas.** Detecta la *forma* (12/15/18/21/24
  palabras seguidas) sin la wordlist BIP39, así que sale como heurística para revisar
  a mano, nunca como certeza.
- **No mira la cadena.** Sin análisis de UTXO, de reutilización de direcciones ni de
  contrapartes: es una decisión de alcance, no una carencia.
- **No sustituye** una auditoría criptográfica ni un proceso profesional de respuesta
  a incidentes.
- Las etapas 9-11 leen la **configuración versionada**, no procesos en ejecución.
