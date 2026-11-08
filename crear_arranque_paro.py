"""
Crea en TIA Portal V17 el arranque y paro de motor en KOP (Ladder), lo compila
y exporta los bloques resultantes.

Uso (desde la carpeta del proyecto, con TIA abierto o cerrado):
    .venv\\Scripts\\python crear_arranque_paro.py              # todo el proceso
    .venv\\Scripts\\python crear_arranque_paro.py --solo-xml   # solo genera XML, sin TIA
    .venv\\Scripts\\python crear_arranque_paro.py --archivar v1_ArranqueParoLadder
"""
import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from programas import arranque_paro as prog  # noqa: E402
from tia.ladder import NS_FLGNET_V17, NS_INTERFAZ_V17  # noqa: E402

DIR_XML = RAIZ / "xml" / "generados"
DIR_EXPORT = RAIZ / "xml" / "exportados"
DIR_TIA = RAIZ / "tia_proyecto"
DIR_ENTREGAS = RAIZ / "entregas"
NOMBRE_PROYECTO = "ArranqueParo"
PLC = "PLC_1"
CPU = "6ES7 214-1AG40-0XB0/V4.5"   # S7-1214C DC/DC/DC, firmware V4.5


def generar_xml(cultura: str, ns_interfaz: str) -> tuple[Path, Path]:
    DIR_XML.mkdir(parents=True, exist_ok=True)
    ns = {"ns_interfaz": ns_interfaz, "ns_flgnet": NS_FLGNET_V17}
    fb = DIR_XML / f"{prog.FB_NOMBRE}.xml"
    ob = DIR_XML / "Main_OB1.xml"
    fb.write_text(prog.xml_fb(cultura, **ns), encoding="utf-8")
    ob.write_text(prog.xml_ob1(cultura, **ns), encoding="utf-8")
    print(f"XML generados en {DIR_XML}")
    return fb, ob


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--solo-xml", action="store_true", help="Solo generar los XML (no abre TIA)")
    ap.add_argument("--archivar", metavar="NOMBRE_VERSION",
                    help="Al final, crear entregas/NOMBRE_VERSION.zap17")
    args = ap.parse_args()

    if args.solo_xml:
        generar_xml("es-ES", NS_INTERFAZ_V17)
        return 0

    from tia import openness as tia_api  # carga Openness solo si hace falta

    tia, iniciado = tia_api.conectar()
    try:
        proyecto = tia_api.abrir_o_crear_proyecto(tia, DIR_TIA, NOMBRE_PROYECTO)
        cultura = tia_api.cultura_edicion(proyecto)
        print(f"Idioma de edición del proyecto: {cultura}")
        plc = tia_api.obtener_o_crear_plc(proyecto, PLC, CPU)

        print("\n[1/5] Tabla de variables")
        tia_api.crear_tabla_tags(plc, prog.TABLA_TAGS, prog.TAGS, proyecto)

        print("\n[2/5] Generando XML KOP")
        ns_interfaz = tia_api.detectar_namespace_interfaz(plc, NS_INTERFAZ_V17)
        xml_fb, xml_ob = generar_xml(cultura, ns_interfaz)

        print("\n[3/5] Importando bloques")
        tia_api.importar_xml(plc, xml_fb)
        tia_api.asegurar_db_instancia(plc, prog.DB_INSTANCIA, prog.FB_NOMBRE)
        tia_api.importar_xml(plc, xml_ob)

        print("\n[4/5] Compilando")
        ok = tia_api.compilar(plc)
        proyecto.Save()
        print("Proyecto guardado.")
        if not ok:
            print("\nHay errores de compilación. Copia este resultado a Claude para corregirlos.")
            return 1

        print("\n[5/5] Exportando bloques compilados (referencia para plantillas)")
        for nombre, archivo in [(prog.FB_NOMBRE, f"{prog.FB_NOMBRE}.xml"), ("Main", "Main_OB1.xml"),
                                (prog.DB_INSTANCIA, f"{prog.DB_INSTANCIA}.xml")]:
            tia_api.exportar_bloque(plc, nombre, DIR_EXPORT / archivo)
            print(f"  -> xml/exportados/{archivo}")

        if args.archivar:
            destino = tia_api.archivar(proyecto, DIR_ENTREGAS, args.archivar)
            print(f"\nVersión archivada: {destino}")

        print("\nLISTO. Siguiente paso: probar en PLCSIM (ver README.md).")
        return 0
    finally:
        if iniciado:
            input("\nTIA fue abierto por este script y se cerrará al terminar. "
                  "Revisa el proyecto y presiona Enter para cerrar...")
        tia.Dispose()


if __name__ == "__main__":
    sys.exit(main())
