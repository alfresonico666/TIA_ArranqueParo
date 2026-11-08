# Cómo trabajamos: Claude Code + MCP TIA V17

## 1. Dónde vive cada cosa

```
C:\Users\LEGION\Proyectos\
├── TIA_MCP_V17\               ← el MCP (herramientas que usa Claude). GitHub PÚBLICO: solo código genérico
├── TIA_ArranqueParo\          ← este repo. GitHub PÚBLICO: solo programas genéricos de práctica
│   ├── v2\                    ← versión actual: especificación + generador + exportado + vistas previas
│   ├── (raíz) tia\, programas\ ← v1 (scripts propios, se conservan como historial)
│   ├── tia_proyecto\          ← proyectos TIA generados (NO va a GitHub; se regeneran)
│   └── entregas\              ← .zap17 de cada versión (NO va a git; se adjunta al GitHub Release)
├── _conocimiento_tia\         ← LO APRENDIDO de proyectos reales (SOLO LOCAL, nunca a GitHub)
│   ├── <proyecto>\PLC_1\...   ← bloques, tags, PERFIL_ESTILO.md
│   ├── <proyecto>\HMI\...     ← pantallas, plantillas, tags HMI
│   └── GUIA_ESTILO_EQUIPO.md  ← guía de estilo PLC + HMI del equipo
├── _referencias\              ← manuales, libros, hojas técnicas (NO va a GitHub)
└── _copias\                   ← COPIAS de proyectos .ap17 de clientes (NO va a GitHub)
```

> Los repos de GitHub son **públicos**: nada de clientes (código, pantallas, nombres de proyecto o logos)
> entra en ellos. Lo aprendido de proyectos reales vive solo en `_conocimiento_tia`.

## 2. Aprender de proyectos anteriores
1. **Tú** copias (no mueves) la carpeta del proyecto a `_copias\`.
2. Le pides a Claude: *"aprende de `_copias\<proyecto>`"*. El MCP abre la copia con su propia instancia
   de TIA, exporta el PLC y la HMI a `_conocimiento_tia\` y cierra sin guardar.
3. Claude lee `PERFIL_ESTILO.md` y las pantallas (`tia_hmi leer`) y sigue ese estilo al programar.

Ya aprendidos dos proyectos de referencia: uno define el aspecto de la HMI y el otro, probado en producción,
la estructura de la HMI y los patrones de ladder. El resumen está en `_conocimiento_tia\GUIA_ESTILO_EQUIPO.md` (solo local).

## 3. Crear un proyecto nuevo (flujo v2)
1. Claude escribe la especificación: tags, bloques, máquinas de estados y pantallas. Por ejemplo, `v2\especificacion.py`.
2. El generador usa el MCP para crear el proyecto, programar, compilar y corregir, y luego exporta y archiva.
3. **Paso manual único por proyecto**: crear la conexión HMI y elegir la pantalla inicial. Openness V17
   no lo permite. Después se vuelve a ejecutar con `--enlazar-plc`.
4. Tú pruebas en PLCSIM más la simulación de la HMI.
5. Si funciona, se hace commit, tag `vN_...` y GitHub Release con el `.zap17`.

También puedes pedirlo conversando con Claude, y él usa directamente las herramientas `tia_*` del MCP.

## 4. Estilos de programación disponibles
| Estilo | Cómo se genera | Cuándo usarlo |
|---|---|---|
| Banderas (S/R) | `tia_programar crear_kop` | Lógica simple, retenciones, como en los proyectos actuales |
| Máquina de estados **Moore** | `tia_programar crear_maquina_estados` (KOP o SCL) | Secuencias de máquina; diagnóstico claro por número de estado |
| Máquina de estados **Mealy** | `tia_programar crear_maquina_estados` (KOP o SCL) | Reacción en el mismo ciclo con menos estados |

## 5. Documentos de referencia
- Guarda los PDF en `_referencias\` (Siemens, Variadores_Servos, Sensores…).
- Pídeselos a Claude de forma concreta, por ejemplo: *"lee el manual del variador en `_referencias\...`"*.

## 6. Versiones (GitHub)
- Nombre: **`vN_DescripcionDeLoAnadido`** (sin espacios, ñ ni acentos).
- Cada versión lleva commit, tag y Release. En este repo el Release adjunta el `.zap17`, que se abre en TIA con *Proyecto > Desarchivar*.
- El MCP también lleva su propio historial de versiones (ver su `CAPACIDADES.md`).

## 7. Cómo probamos
| Nivel | Qué verifica | Quién |
|---|---|---|
| Pruebas offline del MCP | KOP contra los XSD de Siemens, generador HMI, máquinas de estados | Claude |
| Generación en TIA | Importar y compilar el PLC y la HMI con 0 errores | Claude, con el MCP |
| Vista previa | PNG de cada pantalla para revisar el diseño | Claude |
| Simulación | PLCSIM + HMI siguiendo la tabla de pruebas del README de cada versión | Tú, guiado por Claude |
| PLC de banco | Hardware real, **nunca** en una máquina en producción | Tú |
