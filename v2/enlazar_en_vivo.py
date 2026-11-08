"""Enlaza los tags HMI con el PLC EN VIVO, sobre el TIA que el usuario tiene abierto con ArranqueParo_v2.

Requisito: la conexión HMI integrada ya creada a mano (HMI_1 -> PLC_1). El script se adjunta al TIA abierto
(no abre otro ni lo cierra), guarda primero (para no perder la conexión si algo falla), reemplaza la tabla de
tags HMI internos por tags enlazados al PLC, compila PLC y HMI, exporta para Git y guarda. El proyecto queda
abierto para seguir trabajando.

    C:\\Users\\LEGION\\Proyectos\\TIA_MCP_V17\\.venv\\Scripts\\python v2\\enlazar_en_vivo.py [--conexion HMI_Connection_1]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
os.environ.setdefault("TIA_MCP_RUTAS_PERMITIDAS", str(RAIZ / "tia_proyecto"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import especificacion as esp  # noqa: E402
from generar_v2 import DIR_EXPORT, RUTA_AP17, Informe  # noqa: E402
from tia_mcp.openness import conocimiento, hardware, hmi, proyecto  # noqa: E402
from tia_mcp.openness.compilacion import compilar  # noqa: E402
from tia_mcp.openness.sesion import ruta_proyecto  # noqa: E402
from tia_mcp.servidor import crear_servidor  # noqa: E402
from tia_mcp.simaticml.hmi import generador as gen  # noqa: E402


def buscar_pid(s) -> int:
    for p in s.procesos():
        if p.proyecto and Path(p.proyecto).resolve() == RUTA_AP17.resolve():
            return p.pid
    raise SystemExit(f"No encontré un TIA abierto con {RUTA_AP17}. Ábrelo y vuelve a ejecutar.")


def verificar_conexion(s, conexion: str) -> str:
    """Openness no lista las conexiones integradas y, si se importan tags con una conexión inexistente, TIA SE
    CIERRA. Comprobación segura: (1) que no sea una conexión NO integrada (esas sí se listan y no admiten tags
    simbólicos) y (2) que el nombre esté en los datos del proyecto GUARDADO."""
    no_integradas = [str(c.Name) for c in hmi.panel(s).Connections]
    if conexion in no_integradas:
        raise SystemExit(
            f"'{conexion}' es una conexión NO integrada (creada en HMI_1 > Conexiones): no admite tags simbólicos. "
            f"Bórrala y crea la integrada en Dispositivos y redes > Conexiones > Conexión HMI (arrastrar HMI_1 -> "
            f"PLC_1). Se llamará HMI_Connection_1.")
    datos = (RUTA_AP17.parent / "System" / "PEData.plf").read_bytes()
    if conexion.encode("utf-8") not in datos and conexion.encode("utf-16-le") not in datos:
        raise SystemExit(
            f"No encuentro la conexión '{conexion}' en el proyecto guardado. Créala en Dispositivos y redes > "
            f"Conexiones > Conexión HMI (arrastrar HMI_1 -> PLC_1), GUARDA y vuelve a ejecutar. "
            f"(Conexiones no integradas presentes: {', '.join(no_integradas) or 'ninguna'}). "
            f"Si tu conexión tiene otro nombre, usa --conexion <nombre>.")
    return f"Conexión integrada '{conexion}' encontrada en el proyecto guardado."


def tags_enlazados(s, conexion: str) -> str:
    definicion = [{"nombre": n, "tipo": t, "conexion": conexion, "tag_plc": plc, "ciclo": "100 ms"}
                  for n, t, plc in esp.TAGS_HMI]
    xml = gen.tabla_tags_xml(esp.TABLA_TAGS_HMI, definicion, hmi.culturas_proyecto(s))
    importados = hmi.importar(s, hmi.panel(s), "tags", xml)
    return f"Tabla {', '.join(importados)}: {len(definicion)} tags enlazados al PLC por {conexion}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--conexion", default=esp.CONEXION_HMI, help="Nombre de la conexión HMI creada en TIA")
    args = ap.parse_args()
    _, ctx = crear_servidor()
    s, ej, inf = ctx.sesion, ctx.ejecutor.ejecutar_sincrono, Informe()

    pid = ej(buscar_pid, s)
    ej(inf.paso, f"Adjuntarse al TIA del usuario (PID {pid})", s.conectar, True, pid)
    ej(inf.paso, "Proyecto activo", lambda: str(ruta_proyecto(s.proyecto)))
    ej(inf.paso, "Guardar ANTES (protege la conexión HMI recién creada)", proyecto.guardar, s)
    try:
        print(ej(verificar_conexion, s, args.conexion))
    except SystemExit as e:
        print(f"\nDETENIDO (sin tocar nada más): {e}")
        ej(s.desconectar)
        ctx.ejecutor.cerrar()
        return 1
    estado = ej(inf.paso, "Tags HMI -> tags PLC", tags_enlazados, s, args.conexion)
    if estado is None:
        print("\nNo se enlazaron los tags: no se continúa. El proyecto quedó guardado con tu conexión.")
        ej(s.desconectar)
        ctx.ejecutor.cerrar()
        return 1
    plc = ej(inf.paso, "Compilar PLC", lambda: compilar(s, hardware.plc(s, "PLC_1")).resumen())
    hmi_res = ej(inf.paso, "Compilar HMI", lambda: hmi.compilar_panel(s, hmi.panel(s)).resumen())
    ej(inf.paso, "Exportar PLC + HMI para Git", conocimiento.exportar_programa, s, str(DIR_EXPORT))
    ej(inf.paso, "Guardar", proyecto.guardar, s)
    ej(inf.paso, "Soltar TIA (queda abierto para el usuario)", s.desconectar)
    ctx.ejecutor.cerrar()
    print("\n================ RESUMEN")
    print(f"PLC: {(plc or '-').splitlines()[0]}")
    print(f"HMI: {(hmi_res or '-').splitlines()[0]}")
    print("TODO OK" if not inf.errores else "FALLOS:\n  " + "\n  ".join(inf.errores))
    return 1 if inf.errores else 0


if __name__ == "__main__":
    sys.exit(main())
