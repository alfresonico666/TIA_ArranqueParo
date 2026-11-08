# CLAUDE.md – Automatización de TIA Portal V17 con Openness

## Contexto
- Usuario: programador PLC (Siemens), nuevo en Claude Code. Responder **en español** y explicar paso a paso.
- TIA Portal V17 + PLCSIM V17 (sin PLCSIM Advanced). Openness V17 vía **Python + pythonnet** (costo $0; no usar Visual Studio).
- Objetivo: generar programas **KOP/Ladder** como SimaticML XML, importarlos con Openness, compilar y corregir solos.

## Flujo actual (v2+): con el MCP `tia-v17` (repo TIA_MCP_V17)
- Especificación en `v2/especificacion.py`; generador `v2/generar_v2.py`. Se ejecuta con el Python del MCP:
  `C:\Users\LEGION\Proyectos\TIA_MCP_V17\.venv\Scripts\python v2\generar_v2.py [--enlazar-plc] [--archivar vN_...]`.
- Estilo del equipo (LOCAL, no subir): `C:\Users\LEGION\Proyectos\_conocimiento_tia\GUIA_ESTILO_EQUIPO.md` (aspecto de HMI de un proyecto de referencia; estructura y ladder de otro, probado en producción).
- Los repos son PÚBLICOS: nada de clientes (código, pantallas, nombres/códigos de proyecto, logos) en git.
- Conexión HMI integrada y pantalla inicial: manuales 1 vez por proyecto. Usar `--enlazar-plc` SOLO cuando la conexión exista (si no, TIA se cierra al importar los tags).
- Conectar siempre con instancia propia de TIA (el usuario puede tener TIA abierto con originales).

## Estructura v1 (historial)
- `tia/openness.py` – conexión a TIA, proyecto, PLC, tags, importar/exportar, compilar, archivar.
- `tia/ladder.py` – generador SimaticML KOP (Contacto, Bobina, Serie, Paralelo, LlamadaFB, Red).
- `programas/*.py` – definición de cada programa (tags + redes). Un archivo por máquina/práctica.
- `crear_*.py` – scripts que ejecutan todo el flujo en TIA.
- `xml/generados/` – XML que generamos. `xml/exportados/` – lo que TIA devuelve tras compilar (fuente de verdad del formato).
- `plantillas_xml/` – bloques exportados de proyectos anteriores (copias), base para generar nuevos.
- `tests/` – pruebas sin TIA (validación contra XSD de `C:\Program Files\Siemens\Automation\Portal V17\PublicAPI\V17\Schemas`).

## Comandos
- Pruebas offline: `.venv\Scripts\python tests\test_ladder.py`
- Solo XML: `.venv\Scripts\python crear_arranque_paro.py --solo-xml`
- Flujo completo: `.venv\Scripts\python crear_arranque_paro.py [--archivar vN_Descripcion]`

## Reglas
1. **Nunca** abrir con Openness un proyecto original de cliente: solo copias en `C:\Users\LEGION\Proyectos\_copias\`.
2. **Nunca** descargar a una máquina en producción; solo PLCSIM o PLC de banco, y la descarga la confirma el usuario.
3. Si TIA tiene abierto otro proyecto, no tocarlo: pedir al usuario que lo cierre.
4. Antes de importar a TIA, correr `tests/test_ladder.py` (XSD + cableado).
5. Versiones: tag git + GitHub Release con nombre `vN_DescripcionDeLoAñadido` (sin espacios ni ñ/acentos en el tag, ej. `v2_PilotoFallaTermico`). Adjuntar el `.zap17` de `entregas/` al Release.
6. No subir a GitHub: `.venv/`, `tia_proyecto/`, `entregas/`, manuales PDF, copias o exportaciones de proyectos de clientes (`_copias`, `_conocimiento_tia`).
7. Manuales y libros de referencia: `C:\Users\LEGION\Proyectos\_referencias\` (leer de ahí cuando se pida).

## Notas técnicas Openness V17
- Las dependencias de `Siemens.Engineering.dll` están en `Portal V17\Bin\PublicAPI` → se resuelven con `AssemblyResolve` (ya en `openness.py`).
- pythonnet 3 devuelve el tipo declarado: usar `_real(obj)` (`__implementation__`) para obtener el tipo concreto.
- El namespace de `<Sections>` se calibra en vivo (`detectar_namespace_interfaz`). FlgNet: `.../NetworkSource/FlgNet/v4`.
- Exportar requiere el bloque compilado (consistente).
