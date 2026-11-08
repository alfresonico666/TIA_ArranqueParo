"""
Puente entre Python y TIA Portal V17 usando TIA Openness (gratis, viene con TIA).

Requisitos (una sola vez):
  - Tu usuario de Windows en el grupo "Siemens TIA Openness" y haber cerrado
    sesión después de agregarlo.
  - pythonnet instalado en el .venv del proyecto.

La primera vez que un script se conecta, TIA muestra un aviso de seguridad
de Openness: responde "Sí a todo".
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

from pythonnet import load

load("netfx")  # Openness V17 corre sobre .NET Framework 4.8

import clr  # noqa: E402
from System import AppDomain, ResolveEventHandler  # noqa: E402
from System.IO import DirectoryInfo, FileInfo  # noqa: E402
from System.Reflection import Assembly, AssemblyName  # noqa: E402

TIA_DIR = Path(r"C:\Program Files\Siemens\Automation\Portal V17")
DLL_API = TIA_DIR / "PublicAPI" / "V17" / "Siemens.Engineering.dll"
DIR_DEPENDENCIAS = TIA_DIR / "Bin" / "PublicAPI"


def _resolver(sender, args):
    # Siemens.Engineering.dll depende de ensamblados en Bin\PublicAPI;
    # .NET no los encuentra solo, así que se los indicamos.
    ruta = DIR_DEPENDENCIAS / (AssemblyName(args.Name).Name + ".dll")
    return Assembly.LoadFrom(str(ruta)) if ruta.exists() else None


AppDomain.CurrentDomain.AssemblyResolve += ResolveEventHandler(_resolver)
clr.AddReference(str(DLL_API))

from Siemens.Engineering import (  # noqa: E402
    ExportOptions, ImportOptions, ProjectArchivationMode, TiaPortal, TiaPortalMode,
)
from Siemens.Engineering.Compiler import ICompilable  # noqa: E402
from Siemens.Engineering.HW.Features import SoftwareContainer  # noqa: E402
from Siemens.Engineering.SW import PlcSoftware  # noqa: E402
from Siemens.Engineering.SW.Blocks import ProgrammingLanguage  # noqa: E402


def _real(obj):
    """pythonnet 3 devuelve el tipo declarado; esto da el tipo real (p. ej. PlcSoftware)."""
    return getattr(obj, "__implementation__", obj)


# --------------------------------------------------------------------------
# Conexión y proyecto
# --------------------------------------------------------------------------
def conectar() -> tuple[object, bool]:
    """Se conecta a un TIA abierto; si no hay, abre uno con interfaz visible.

    Devuelve (tia, iniciado_por_nosotros).
    """
    procesos = list(TiaPortal.GetProcesses())
    if procesos:
        print(f"Conectando al TIA Portal abierto (PID {procesos[0].Id})...")
        return procesos[0].Attach(), False
    print("No hay TIA abierto. Iniciando TIA Portal V17 con interfaz (tarda ~1 min)...")
    return TiaPortal(TiaPortalMode.WithUserInterface), True


def abrir_o_crear_proyecto(tia, carpeta: Path, nombre: str):
    """Reutiliza el proyecto si ya está abierto o existe; si no, lo crea."""
    ruta_ap17 = carpeta / nombre / f"{nombre}.ap17"
    abiertos = list(tia.Projects)
    for p in abiertos:
        if Path(str(p.Path.FullName)).resolve() == ruta_ap17.resolve():
            print(f"Proyecto ya abierto: {ruta_ap17}")
            return p
    if abiertos:
        raise RuntimeError(
            "TIA tiene abierto OTRO proyecto. Ciérralo (sin guardar cambios que no quieras) "
            "y vuelve a ejecutar, para no modificarlo por accidente."
        )
    if ruta_ap17.exists():
        print(f"Abriendo proyecto existente: {ruta_ap17}")
        return tia.Projects.Open(FileInfo(str(ruta_ap17)))
    carpeta.mkdir(parents=True, exist_ok=True)
    print(f"Creando proyecto nuevo: {ruta_ap17}")
    return tia.Projects.Create(DirectoryInfo(str(carpeta)), nombre)


def cultura_edicion(proyecto) -> str:
    """Idioma de edición del proyecto (p. ej. 'es-ES'), para los comentarios."""
    try:
        return str(proyecto.LanguageSettings.EditingLanguage.Culture.Name)
    except Exception:
        return "es-ES"


def obtener_o_crear_plc(proyecto, nombre: str, referencia: str):
    """Devuelve el PlcSoftware del PLC `nombre`; crea la CPU si no existe."""
    plc = buscar_plc(proyecto, nombre)
    if plc is not None:
        print(f"PLC encontrado: {nombre}")
        return plc
    print(f"Agregando CPU {referencia} como '{nombre}'...")
    proyecto.Devices.CreateWithItem(f"OrderNumber:{referencia}", nombre, nombre)
    plc = buscar_plc(proyecto, nombre)
    if plc is None:
        raise RuntimeError("Se creó el dispositivo pero no se encontró su software PLC")
    return plc


def buscar_plc(proyecto, nombre: str | None = None):
    for dispositivo in proyecto.Devices:
        for item in _items_recursivos(dispositivo.DeviceItems):
            sc = item.GetService[SoftwareContainer]()
            if sc is None:
                continue
            sw = _real(sc.Software)
            if isinstance(sw, PlcSoftware) and (nombre is None or str(sw.Name) == nombre
                                                or str(dispositivo.Name) == nombre):
                return sw
    return None


def _items_recursivos(items):
    for it in items:
        yield it
        yield from _items_recursivos(it.DeviceItems)


# --------------------------------------------------------------------------
# Variables, bloques, compilación
# --------------------------------------------------------------------------
def crear_tabla_tags(plc, nombre_tabla: str, tags: list[tuple[str, str, str, str]], proyecto=None):
    """tags = [(nombre, tipo, dirección, comentario), ...]. Idempotente."""
    tabla = plc.TagTableGroup.TagTables.Find(nombre_tabla) \
        or plc.TagTableGroup.TagTables.Create(nombre_tabla)
    idioma = proyecto.LanguageSettings.EditingLanguage if proyecto is not None else None
    for nombre, tipo, direccion, comentario in tags:
        tag = tabla.Tags.Find(nombre)
        if tag is None:
            tag = tabla.Tags.Create(nombre, tipo, direccion)
            print(f"  + tag {nombre:<12} {tipo:<5} {direccion}")
        else:
            tag.DataTypeName = tipo
            tag.LogicalAddress = direccion
            print(f"  = tag {nombre:<12} {tipo:<5} {direccion} (actualizado)")
        if comentario and idioma is not None:
            try:
                tag.Comment.Items.Find(idioma).Text = comentario
            except Exception:
                pass  # el comentario es opcional
    return tabla


def importar_xml(plc, archivo: Path):
    """Importa un bloque SimaticML, reemplazando si ya existe."""
    print(f"Importando {archivo.name}...")
    bloques = plc.BlockGroup.Blocks.Import(FileInfo(str(archivo)), ImportOptions.Override)
    return [str(b.Name) for b in bloques]


def asegurar_db_instancia(plc, nombre_db: str, nombre_fb: str):
    if plc.BlockGroup.Blocks.Find(nombre_db) is None:
        print(f"Creando DB de instancia {nombre_db} para {nombre_fb}...")
        plc.BlockGroup.Blocks.CreateInstanceDB(nombre_db, True, 1, nombre_fb)


def compilar(plc) -> bool:
    """Compila el software del PLC y muestra errores/advertencias. True si 0 errores."""
    print("Compilando software del PLC...")
    resultado = plc.GetService[ICompilable]().Compile()
    print(f"Resultado: {resultado.State} | errores: {resultado.ErrorCount} | "
          f"advertencias: {resultado.WarningCount}")
    _imprimir_mensajes(resultado.Messages, 1)
    return resultado.ErrorCount == 0


def _imprimir_mensajes(mensajes, nivel):
    for m in mensajes:
        estado = str(m.State)
        if estado in ("Error", "Warning") or m.ErrorCount or m.WarningCount:
            texto = str(m.Description or "").strip()
            print(f"{'  ' * nivel}[{estado}] {m.Path}: {texto}")
        _imprimir_mensajes(m.Messages, nivel + 1)


def exportar_bloque(plc, nombre: str, destino: Path):
    """Exporta un bloque a SimaticML (debe estar compilado)."""
    bloque = plc.BlockGroup.Blocks.Find(nombre)
    if bloque is None:
        raise RuntimeError(f"No existe el bloque {nombre}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        destino.unlink()
    bloque.Export(FileInfo(str(destino)), ExportOptions.WithDefaults)


def detectar_namespace_interfaz(plc, defecto: str) -> str:
    """Calibración: crea un FB vacío en KOP, lo exporta y lee qué namespace
    de interfaz usa ESTA instalación de TIA. Luego borra el bloque."""
    nombre = "ZZ_Calibracion_Openness"
    try:
        bloque = plc.BlockGroup.Blocks.Find(nombre) \
            or plc.BlockGroup.Blocks.CreateFB(nombre, True, 1, ProgrammingLanguage.LAD)
        compilar_silencioso(plc)
        tmp = Path(tempfile.gettempdir()) / f"{nombre}.xml"
        if tmp.exists():
            tmp.unlink()
        bloque.Export(FileInfo(str(tmp)), ExportOptions.WithDefaults)
        texto = tmp.read_text(encoding="utf-8-sig")
        tmp.unlink()
        bloque.Delete()
        m = re.search(r'xmlns="(http://www\.siemens\.com/automation/Openness/SW/Interface/v\d+)"', texto)
        if m:
            print(f"Namespace de interfaz detectado: {m.group(1)}")
            return m.group(1)
    except Exception as e:  # la calibración nunca debe detener el proceso
        print(f"(Calibración omitida: {e})")
        b = plc.BlockGroup.Blocks.Find(nombre)
        if b is not None:
            b.Delete()
    print(f"Usando namespace por defecto: {defecto}")
    return defecto


def compilar_silencioso(plc):
    plc.GetService[ICompilable]().Compile()


def archivar(proyecto, carpeta: Path, nombre: str) -> Path:
    """Crea un .zap17 (proyecto archivado) para entregar una versión."""
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f"{nombre}.zap17"
    if destino.exists():
        destino.unlink()
    proyecto.Archive(DirectoryInfo(str(carpeta)), f"{nombre}.zap17", ProjectArchivationMode.Compressed)
    return destino
