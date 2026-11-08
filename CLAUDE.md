# CLAUDE.md – Automatización de TIA Portal V17 con Openness

## Contexto
- Usuario: programador PLC (Siemens), nuevo en Claude Code. Responder **en español** y explicar paso a paso.
- TIA Portal V17 + PLCSIM V17 (sin PLCSIM Advanced). Openness V17 vía **Python + pythonnet** (costo $0; no usar Visual Studio).
- Objetivo: generar programas **KOP/Ladder** como SimaticML XML, importarlos con Openness, compilar y corregir solos.

## Estructura
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
6. No subir a GitHub: `.venv/`, `tia_proyecto/`, `entregas/`, manuales PDF, copias de proyectos de clientes.
7. Manuales y libros de referencia: `C:\Users\LEGION\Proyectos\_referencias\` (leer de ahí cuando se pida).

## Notas técnicas Openness V17
- Las dependencias de `Siemens.Engineering.dll` están en `Portal V17\Bin\PublicAPI` → se resuelven con `AssemblyResolve` (ya en `openness.py`).
- pythonnet 3 devuelve el tipo declarado: usar `_real(obj)` (`__implementation__`) para obtener el tipo concreto.
- El namespace de `<Sections>` se calibra en vivo (`detectar_namespace_interfaz`). FlgNet: `.../NetworkSource/FlgNet/v4`.
- Exportar requiere el bloque compilado (consistente).
