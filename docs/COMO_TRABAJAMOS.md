# Cómo trabajamos: Claude Code + TIA Portal V17

## 1. Dónde vive cada cosa

```
C:\Users\LEGION\Proyectos\
├── TIA_ArranqueParo\          ← ESTE repositorio (va a GitHub, privado)
│   ├── tia\                   ← motor: openness.py (TIA) y ladder.py (generador KOP)
│   ├── programas\             ← un .py por programa/máquina (tags + redes)
│   ├── plantillas_xml\        ← bloques KOP exportados de proyectos anteriores
│   ├── xml\generados\         ← XML que genera Claude
│   ├── xml\exportados\        ← XML que devuelve TIA tras compilar (formato real)
│   ├── tests\                 ← pruebas sin TIA (esquemas XSD de Siemens)
│   ├── tia_proyecto\          ← proyecto TIA de prueba (NO va a GitHub; se regenera)
│   └── entregas\              ← .zap17 de cada versión (NO va a git; se sube al Release)
├── _referencias\              ← manuales, libros, hojas técnicas (NO va a GitHub)
│   ├── Siemens\
│   ├── Variadores_Servos\
│   └── Sensores\
└── _copias\                   ← COPIAS de proyectos .ap17 para extraer plantillas (NO va a GitHub)
```

## 2. Proyectos de plantilla (tus programas anteriores)
1. **Tú** copias la carpeta completa de un proyecto anterior a `_copias\`. Ejemplo: `Desktop\Alfredo\Documentacion Maquinas\25HA095\...\25HA095_RevFinal` se copia a `_copias\25HA095_RevFinal`.
   El original nunca se toca. Openness solo abre la copia.
2. Le dices a Claude: *"exporta los bloques KOP de `_copias\25HA095_RevFinal` a plantillas"*.
3. Claude ejecuta un script de exportación. Cada FB/FC/OB queda como XML en `plantillas_xml\25HA095\`.
4. Claude estudia esos XML: tu estilo de nombres, tus FB típicos (motores, válvulas, alarmas) y las instrucciones que usas (TON, CTU, MOVE, comparadores). Con eso amplía `tia\ladder.py` para generar lo mismo.
5. A partir de ahí le pides, por ejemplo: *"genera 3 motores con arranque y paro y una alarma de térmico, al estilo de 25HA095"*.

## 3. Documentos de referencia (manuales y libros)
- Guarda los PDF en `C:\Users\LEGION\Proyectos\_referencias\`, ordenados por fabricante o equipo.
- Claude puede leer PDF directamente. Pídeselo de forma concreta: *"lee el manual del variador en `_referencias\Variadores_Servos\` y dime qué palabras de control usa por PROFINET"*.
- Estos archivos no se suben a GitHub por su tamaño y por derechos de autor.

## 4. Versiones (GitHub)
- **Repositorio privado** en tu cuenta de GitHub.
- Cada entrega lleva un nombre con el formato **`vN_DescripcionDeLoAñadido`**:
  - `v1_ArranqueParoLadder`
  - `v2_PilotoFallaTermico`
  - `v3_PlantillasDe25HA095`
- Cada versión consta de un **commit**, un **tag de git** con ese nombre y un **GitHub Release** con el `.zap17` adjunto. Ese archivo se abre directo en TIA: *Proyecto > Desarchivar*.
- En los tags se evitan espacios, ñ y acentos (`Anadido`, no `Añadido`) para que funcionen en cualquier herramienta.
- Para volver a una versión anterior: `git checkout v1_ArranqueParoLadder`, o descargar su `.zap17` desde GitHub.

## 5. Cómo probamos
| Nivel | Qué verifica | Quién lo hace |
|---|---|---|
| 1. Pruebas offline | El XML cumple los esquemas XSD de Siemens y el cableado del escalón es coherente | Claude (`tests\test_ladder.py`) |
| 2. Importar y compilar | TIA acepta los bloques: 0 errores de compilación | Claude (script) |
| 3. Simulación | La lógica funciona en PLCSIM V17 con la tabla de pruebas del README | Tú, guiado por Claude |
| 4. PLC de banco (opcional) | Prueba con hardware real, nunca en una máquina en producción | Tú |

## 6. Ciclo típico de trabajo
1. Le pides algo a Claude, por ejemplo: *"agrega un piloto de falla en Q0.1"*.
2. Claude modifica `programas\*.py` y ejecuta las pruebas offline.
3. Claude ejecuta el script: importa a TIA, compila y corrige si hay errores.
4. Tú pruebas en PLCSIM.
5. Si funciona: commit + tag `vN_...` + Release en GitHub.
