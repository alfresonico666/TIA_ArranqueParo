"""Genera el Arranque y paro v2 (PLC 1214C + HMI KTP400) en TIA Portal V17 usando TIA_MCP_V17.

Usa las mismas funciones que las herramientas MCP (tia_proyecto, tia_tags, tia_programar,
tia_hmi...) para que el resultado sea reproducible y versionable.

Ejecutar con el Python del MCP (desde la carpeta TIA_ArranqueParo):
    C:\\Users\\LEGION\\Proyectos\\TIA_MCP_V17\\.venv\\Scripts\\python v2\\generar_v2.py
    ...\\python v2\\generar_v2.py --archivar v2_ArranqueParoHMIEstilos

1.ª vez: crea el proyecto. Openness V17 no puede crear la conexión HMI ni elegir la pantalla inicial:
    abre tia_proyecto\\ArranqueParo_v2 en TIA, crea la conexión HMI y la pantalla inicial (ver README) y
    vuelve a ejecutar: el script detecta la conexión y enlaza los tags HMI con el PLC.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CARPETA_TIA = RAIZ / "tia_proyecto"
os.environ.setdefault("TIA_MCP_RUTAS_PERMITIDAS", str(CARPETA_TIA))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import especificacion as esp  # noqa: E402
from tia_mcp.errores import ErrorTia  # noqa: E402
from tia_mcp.openness import bloques, conocimiento, hardware, hmi, proyecto, red, tags  # noqa: E402
from tia_mcp.openness.compilacion import compilar  # noqa: E402
from tia_mcp.servidor import crear_servidor  # noqa: E402
from tia_mcp.simaticml.estilos import maquina_estados as me  # noqa: E402
from tia_mcp.simaticml.hmi import generador as gen  # noqa: E402

RUTA_AP17 = CARPETA_TIA / esp.PROYECTO / f"{esp.PROYECTO}.ap17"
DIR_EXPORT = Path(__file__).resolve().parent / "exportado"
DIR_ENTREGAS = RAIZ / "entregas"


class Informe:
    def __init__(self) -> None:
        self.errores: list[str] = []

    def paso(self, titulo: str, funcion, *args, **kwargs):
        inicio = time.time()
        print(f"\n=== {titulo}", flush=True)
        try:
            r = funcion(*args, **kwargs)
            texto = r if isinstance(r, str) else "\n".join(map(str, r or []))
            if texto:
                print(texto[:4000])
            print(f"--- OK ({time.time() - inicio:.1f} s)", flush=True)
            return r
        except Exception as e:
            self.errores.append(f"{titulo}: {e}")
            print(f"--- FALLO: {e}", flush=True)
            return None


def idiomas(s) -> str:
    """es-MX como idioma de edición + en-US (como en los proyectos del equipo)."""
    from System.Globalization import CultureInfo  # noqa: PLC0415 - .NET disponible tras cargar Openness
    ajustes = s.proyecto.LanguageSettings
    esmx = ajustes.Languages.Find(CultureInfo("es-MX"))
    if esmx not in list(ajustes.ActiveLanguages):
        ajustes.ActiveLanguages.Add(esmx)
    ajustes.EditingLanguage = esmx
    ajustes.ReferenceLanguage = esmx
    return f"Idiomas: {[str(i.Culture.Name) for i in ajustes.ActiveLanguages]}, edición es-MX"


def crear_o_abrir(s) -> str:
    if RUTA_AP17.exists():
        return proyecto.abrir(s, str(RUTA_AP17))
    resultado = [proyecto.crear(s, str(CARPETA_TIA), esp.PROYECTO), idiomas(s),
                 hardware.agregar_plc(s, "PLC_1", esp.CPU), hmi.agregar_panel(s, "HMI_1", esp.PANEL),
                 *red.configurar_interfaz(s, "PLC_1", esp.IP_PLC), *red.configurar_interfaz(s, "HMI_1", esp.IP_HMI),
                 hmi.conectar_a_plc(s, "HMI_1", "PLC_1")]
    return "\n".join(resultado)


def tags_hmi(s, externos: bool) -> str:
    definicion = [{"nombre": n, "tipo": t, **({"conexion": esp.CONEXION_HMI, "tag_plc": plc} if externos else {}),
                   "ciclo": "100 ms"} for n, t, plc in esp.TAGS_HMI]
    xml = gen.tabla_tags_xml(esp.TABLA_TAGS_HMI, definicion, hmi.culturas_proyecto(s))
    return ", ".join(hmi.importar(s, hmi.panel(s), "tags", xml))


def enlazar_tags_hmi(s, enlazar: bool) -> str:
    """Con --enlazar-plc: tags EXTERNOS (simbólicos al PLC por la conexión HMI). Sin él: tags INTERNOS para
    previsualizar. NO se "tantea": importar tags externos sin la conexión hace que TIA se cierre."""
    if enlazar:
        return f"Tags HMI ENLAZADOS al PLC por {esp.CONEXION_HMI}: {tags_hmi(s, externos=True)}"
    return ("Tags HMI INTERNOS (sin enlace al PLC). Cuando exista la conexión HMI, ejecuta con --enlazar-plc: "
            f"{tags_hmi(s, externos=False)}")


def main() -> int:  # noqa: PLR0915 - guion lineal
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--archivar", metavar="VERSION", help="Crear entregas/VERSION.zap17 al final")
    ap.add_argument("--interfaz", action="store_true", help="Ver TIA mientras trabaja")
    ap.add_argument("--enlazar-plc", action="store_true",
                    help="La conexión HMI_Connection_1 YA existe: enlazar los tags HMI al PLC")
    args = ap.parse_args()

    _, ctx = crear_servidor()
    s, ej, inf, prog = ctx.sesion, ctx.ejecutor.ejecutar_sincrono, Informe(), ctx.programador

    def plc():
        return hardware.plc(s, "PLC_1")

    ej(inf.paso, "Conectar (instancia propia de TIA)", s.conectar, args.interfaz, None, True)
    ej(inf.paso, "Proyecto ArranqueParo_v2", crear_o_abrir, s)
    for tabla, definiciones in esp.TABLAS_TAGS.items():
        ej(inf.paso, f"Tags PLC: {tabla}", lambda t=tabla, d=definiciones: tags.crear_o_actualizar(s, plc(), t, d))
    c = esp.CARPETA_BLOQUES
    ej(inf.paso, "DB_HMI (datos para la HMI)", lambda: prog.importar_scl(plc(), esp.DB_HMI, c))
    ej(inf.paso, "FB_Mando_Motor (KOP)", lambda: prog.crear_kop(plc(), esp.FB_MANDO, c))
    ej(inf.paso, "Estilo 1: FB_Motor_Banderas (KOP)", lambda: prog.crear_kop(plc(), esp.FB_BANDERAS, c))
    ej(inf.paso, "Estilo 2: FB_Motor_Moore (KOP)",
       lambda: prog.crear_kop(plc(), me.a_kop(me.leer_maquina(esp.MAQUINA_MOORE)), c))
    ej(inf.paso, "Estilo 3: FB_Motor_Mealy (SCL)",
       lambda: prog.importar_scl(plc(), me.a_scl(me.leer_maquina(esp.MAQUINA_MEALY)), c))
    for db, fb in esp.INSTANCIAS.items():
        ej(inf.paso, f"DB de instancia {db}", lambda d=db, f=fb: (
            f"{d} ya existe" if bloques_existe(plc(), d) else bloques.crear_db_instancia(plc(), d, f)))
    ej(inf.paso, "OB1 Main (director KOP)", lambda: prog.crear_kop(plc(), esp.MAIN))
    resultado_plc = ej(inf.paso, "Compilar PLC", lambda: compilar(s, plc()).resumen())
    for nombre, entradas in esp.LISTAS.items():
        ej(inf.paso, f"HMI lista de textos {nombre}", lambda n=nombre, e=entradas: hmi.importar(
            s, hmi.panel(s), "lista_textos", gen.lista_textos_xml(n, e, hmi.culturas_proyecto(s))))
    # Guardar antes de los tags: si la conexión no existiera de verdad, TIA se cerraría al importarlos.
    ej(inf.paso, "Guardar (antes de los tags HMI)", proyecto.guardar, s)
    estado_tags = ej(inf.paso, "HMI tags", enlazar_tags_hmi, s, args.enlazar_plc)
    for pantalla in esp.PANTALLAS:
        ej(inf.paso, f"HMI pantalla {pantalla['nombre']}", lambda p=pantalla: hmi.importar(
            s, hmi.panel(s), "pantalla", gen.pantalla_xml(p, hmi.culturas_proyecto(s))))
    resultado_hmi = ej(inf.paso, "Compilar HMI", lambda: hmi.compilar_panel(s, hmi.panel(s)).resumen())
    ej(inf.paso, "Exportar PLC + HMI para Git", conocimiento.exportar_programa, s, str(DIR_EXPORT))
    ej(inf.paso, "Guardar", proyecto.guardar, s)
    if args.archivar:
        ej(inf.paso, "Archivar entrega", proyecto.archivar, s, str(DIR_ENTREGAS), args.archivar)
    ej(inf.paso, "Cerrar proyecto", proyecto.cerrar, s)
    ej(inf.paso, "Cerrar TIA propio", s.desconectar)
    ctx.ejecutor.cerrar()

    print("\n================ RESUMEN")
    print(f"PLC: {(resultado_plc or 'sin compilar').splitlines()[0]}")
    print(f"HMI: {(resultado_hmi or 'sin compilar').splitlines()[0]}")
    print(f"Tags HMI: {(estado_tags or '-')[:160]}")
    print("TODO OK" if not inf.errores else "FALLOS:\n  " + "\n  ".join(inf.errores))
    return 1 if inf.errores else 0


def bloques_existe(plc, nombre: str) -> bool:
    try:
        bloques.buscar(plc, nombre)
        return True
    except ErrorTia:
        return False


if __name__ == "__main__":
    sys.exit(main())
