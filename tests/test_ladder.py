"""
Pruebas sin TIA: valida que el XML generado cumpla los esquemas XSD oficiales
de Siemens (instalados con TIA V17) y que el cableado del escalón sea coherente.

Ejecutar:  .venv\\Scripts\\python -m pytest -q      (o)   .venv\\Scripts\\python tests\\test_ladder.py
"""
import sys
from pathlib import Path

from lxml import etree

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from programas import arranque_paro as prog  # noqa: E402
from tia.ladder import (  # noqa: E402
    Bobina, Contacto, G, Paralelo, Serie, flgnet,
)

XSD_DIR = Path(r"C:\Program Files\Siemens\Automation\Portal V17\PublicAPI\V17\Schemas")


def _sin_namespace(elem):
    """Los XSD de Siemens no declaran targetNamespace: quitamos el xmlns para validar."""
    copia = etree.fromstring(etree.tostring(elem))
    for e in copia.iter():
        if isinstance(e.tag, str) and "}" in e.tag:
            e.tag = e.tag.split("}", 1)[1]
    etree.cleanup_namespaces(copia)
    return copia


def _esquema(nombre):
    return etree.XMLSchema(etree.parse(str(XSD_DIR / nombre)))


def _validar_documento(xml_texto: str):
    doc = etree.fromstring(xml_texto.encode("utf-8"))
    esquema_lad = _esquema("SW.PlcBlocks.LADFBD_v4.xsd")
    esquema_if = _esquema("SW.InterfaceSections_v4.xsd")
    redes = [e for e in doc.iter() if isinstance(e.tag, str) and e.tag.endswith("FlgNet")]
    assert redes, "El documento no tiene ningún FlgNet"
    for red in redes:
        limpio = _sin_namespace(red)
        assert esquema_lad.validate(limpio), esquema_lad.error_log
        _validar_cableado(limpio)
    secciones = [e for e in doc.iter() if isinstance(e.tag, str) and e.tag.endswith("Sections")]
    assert len(secciones) == 1
    limpio = _sin_namespace(secciones[0])
    assert esquema_if.validate(limpio), esquema_if.error_log
    return doc


def _validar_cableado(red):
    uids_piezas = {int(e.get("UId")) for e in red.find("Parts")}
    # UIds que DEFINEN objetos (NameCon/IdentCon solo los referencian)
    todos_uids = [int(e.get("UId")) for e in red.iter()
                  if e.tag in ("Access", "Part", "Call", "Instance", "Wire")]
    assert len(todos_uids) == len(set(todos_uids)), "UIds repetidos"
    destinos = set()
    for cable in red.find("Wires"):
        hijos = list(cable)
        assert len(hijos) >= 2, "Cable con un solo extremo"
        for c in hijos:
            if c.tag in ("NameCon", "IdentCon"):
                assert int(c.get("UId")) in uids_piezas, f"Cable apunta a UId inexistente {c.get('UId')}"
        for c in hijos[1:]:
            clave = (c.tag, c.get("UId"), c.get("Name"))
            assert clave not in destinos, f"Pin alimentado dos veces: {clave}"
            destinos.add(clave)
    # cada pieza Contact/Coil debe tener 'in' y 'operand' conectados
    for p in red.find("Parts"):
        if p.tag == "Part" and p.get("Name") in ("Contact", "Coil", "SCoil", "RCoil"):
            for pin in ("in", "operand"):
                assert ("NameCon", p.get("UId"), pin) in destinos, f"Pin {pin} de {p.get('UId')} sin conectar"


def test_fb_arranque_paro_cumple_xsd():
    doc = _validar_documento(prog.xml_fb())
    assert doc.find("SW.Blocks.FB/AttributeList/ProgrammingLanguage").text == "LAD"


def test_ob1_cumple_xsd():
    doc = _validar_documento(prog.xml_ob1())
    assert doc.find("SW.Blocks.OB/AttributeList/SecondaryType").text == "ProgramCycle"


def test_retencion_tiene_or_de_dos_ramas():
    red = etree.fromstring(flgnet(Serie(
        Paralelo(Contacto(G("A")), Contacto(G("B"))), Bobina(G("C")))).encode())
    ors = [p for p in red.iter("{*}Part") if p.get("Name") == "O"]
    assert len(ors) == 1 and ors[0].findtext("{*}TemplateValue") == "2"


def test_ids_de_documento_unicos():
    for xml in (prog.xml_fb(), prog.xml_ob1()):
        doc = etree.fromstring(xml.encode("utf-8"))
        ids = [e.get("ID") for e in doc.iter() if e.get("ID") is not None]
        assert len(ids) == len(set(ids))


if __name__ == "__main__":
    fallos = 0
    for nombre, f in list(globals().items()):
        if nombre.startswith("test_") and callable(f):
            try:
                f()
                print(f"OK    {nombre}")
            except AssertionError as e:
                fallos += 1
                print(f"FALLA {nombre}: {e}")
    sys.exit(1 if fallos else 0)
