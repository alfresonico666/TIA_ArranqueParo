"""Importa las pantallas de la HMI (especificacion.py) EN VIVO sobre el TIA abierto con ArranqueParo_v2.

Comprueba antes que el panel sea el de especificacion.PANEL (KTP700): si no, no toca nada. Después compila la
HMI, exporta para Git y guarda. El proyecto queda abierto.

    C:\\Users\\LEGION\\Proyectos\\TIA_MCP_V17\\.venv\\Scripts\\python v2\\aplicar_pantallas_en_vivo.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
os.environ.setdefault("TIA_MCP_RUTAS_PERMITIDAS", str(RAIZ / "tia_proyecto"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import especificacion as esp  # noqa: E402
from generar_v2 import DIR_EXPORT, Informe  # noqa: E402
from tia_mcp.openness import conocimiento, hardware, hmi, proyecto  # noqa: E402
from tia_mcp.servidor import crear_servidor  # noqa: E402
from tia_mcp.simaticml.hmi import generador as gen  # noqa: E402


def panel_actual(s) -> str:
    for d in hardware.dispositivos(s):
        if d.nombre == "HMI_1":
            return next((m.referencia for m in d.modulos if m.referencia.startswith("6AV2")), "?")
    return "?"


def main() -> int:
    _, ctx = crear_servidor()
    s, ej, inf = ctx.sesion, ctx.ejecutor.ejecutar_sincrono, Informe()
    pid = [p.pid for p in ej(s.procesos) if p.proyecto and "ArranqueParo_v2" in p.proyecto]
    if not pid:
        sys.exit("No hay un TIA abierto con ArranqueParo_v2.")
    ej(inf.paso, f"Adjuntarse a tu TIA (PID {pid[0]})", s.conectar, True, pid[0])
    referencia = ej(panel_actual, s)
    if referencia != esp.PANEL:
        print(f"\nDETENIDO: HMI_1 es '{referencia}' y se espera '{esp.PANEL}'. Haz en TIA: clic derecho en HMI_1 → "
              f"Cambiar dispositivo → KTP700 Basic PN ({esp.PANEL.split('/')[0]}), versión 17.0.0.0; guarda y repite.")
        ej(s.desconectar)
        ctx.ejecutor.cerrar()
        return 1
    print(f"Panel correcto: {referencia}")
    ej(inf.paso, "Guardar antes", proyecto.guardar, s)
    for p in esp.PANTALLAS:
        ej(inf.paso, f"Pantalla {p['nombre']}", lambda p=p: hmi.importar(
            s, hmi.panel(s), "pantalla", gen.pantalla_xml(p, hmi.culturas_proyecto(s))))
    resultado = ej(inf.paso, "Compilar HMI", lambda: hmi.compilar_panel(s, hmi.panel(s)).resumen())
    ej(inf.paso, "Exportar para Git", conocimiento.exportar_programa, s, str(DIR_EXPORT))
    ej(inf.paso, "Guardar", proyecto.guardar, s)
    ej(inf.paso, "Soltar TIA (queda abierto)", s.desconectar)
    ctx.ejecutor.cerrar()
    print("\nHMI:", (resultado or "-").splitlines()[0])
    print("TODO OK" if not inf.errores else "FALLOS:\n  " + "\n  ".join(inf.errores))
    return 1 if inf.errores else 0


if __name__ == "__main__":
    sys.exit(main())
