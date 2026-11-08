"""
Generador de bloques KOP (Ladder) en formato SimaticML para TIA Portal V17.

No necesita TIA abierto: solo arma el texto XML. Luego `tia/openness.py`
lo importa al proyecto.

Idea básica: describes la lógica con objetos de Python y el generador
calcula las piezas (Parts) y los cables (Wires) que TIA espera.

    Serie(
        Paralelo(Contacto(G("Marcha")), Contacto(G("Motor"))),   # retención
        Contacto(G("Paro_NC")),
        Contacto(G("Termico_NC")),
        Bobina(G("Motor")),
    )

equivale al escalón:

    |--+--[ Marcha ]--+--[ Paro_NC ]--[ Termico_NC ]--( Motor )--|
       +--[ Motor  ]--+
"""
from __future__ import annotations

from dataclasses import dataclass, field
from xml.sax.saxutils import escape, quoteattr

# Namespaces de SimaticML. El de la interfaz se calibra contra TIA en
# tiempo de ejecución (ver openness.detectar_namespace_interfaz); este es
# solo el valor por defecto para V17.
NS_INTERFAZ_V17 = "http://www.siemens.com/automation/Openness/SW/Interface/v5"
NS_FLGNET_V17 = "http://www.siemens.com/automation/Openness/SW/NetworkSource/FlgNet/v4"


# --------------------------------------------------------------------------
# Elementos de la lógica
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Operando:
    """Una variable usada en el escalón."""
    nombre: str
    global_: bool = True  # True = tag global ("Marcha"), False = local (#Marcha)


def G(nombre: str) -> Operando:
    """Tag global de la tabla de variables PLC. Ej: G("Marcha")."""
    return Operando(nombre, True)


def L(nombre: str) -> Operando:
    """Variable local de la interfaz del bloque. Ej: L("Marcha") -> #Marcha."""
    return Operando(nombre, False)


@dataclass
class Contacto:
    """Contacto normalmente abierto --[ ]--, o cerrado --[/]-- si negado=True."""
    operando: Operando
    negado: bool = False


@dataclass
class Bobina:
    """Bobina --( )--. tipo: 'Coil' (normal), 'SCoil' (Set), 'RCoil' (Reset)."""
    operando: Operando
    tipo: str = "Coil"


@dataclass
class Serie:
    elementos: list

    def __init__(self, *elementos):
        self.elementos = list(elementos)


@dataclass
class Paralelo:
    ramas: list

    def __init__(self, *ramas):
        if len(ramas) < 2:
            raise ValueError("Un Paralelo necesita al menos 2 ramas")
        self.ramas = list(ramas)


@dataclass
class Param:
    """Parámetro de una llamada a FB/FC."""
    seccion: str          # "Input", "Output" o "InOut"
    operando: Operando
    tipo: str = "Bool"


@dataclass
class LlamadaFB:
    """Caja de llamada a un FB con su DB de instancia."""
    fb: str
    instancia: str
    parametros: dict[str, Param] = field(default_factory=dict)


@dataclass
class Red:
    """Un segmento (network) del bloque KOP."""
    titulo: str
    logica: object
    comentario: str = ""


@dataclass
class Variable:
    """Variable de la interfaz de un bloque."""
    nombre: str
    tipo: str = "Bool"
    comentario: str = ""


# --------------------------------------------------------------------------
# Construcción del FlgNet (piezas + cables)
# --------------------------------------------------------------------------
POWERRAIL = ("powerrail",)


class _Red:
    def __init__(self):
        self._uid = 20
        self.accesos: list[str] = []
        self.piezas: list[str] = []
        self.cables: dict[tuple, list[tuple]] = {}  # origen -> destinos

    def uid(self) -> int:
        self._uid += 1
        return self._uid

    def conectar(self, origen, destino):
        self.cables.setdefault(origen, []).append(destino)

    def acceso(self, op: Operando) -> int:
        u = self.uid()
        alcance = "GlobalVariable" if op.global_ else "LocalVariable"
        self.accesos.append(
            f'<Access Scope="{alcance}" UId="{u}"><Symbol>'
            f"<Component Name={quoteattr(op.nombre)} />"
            f"</Symbol></Access>"
        )
        return u

    # Devuelve el "pin" de salida del elemento, que alimenta al siguiente.
    def emitir(self, elem, entrada):
        if isinstance(elem, Contacto):
            u = self.uid()
            neg = '<Negated Name="operand" />' if elem.negado else ""
            self.piezas.append(f'<Part Name="Contact" UId="{u}">{neg}</Part>'
                               if neg else f'<Part Name="Contact" UId="{u}" />')
            self.conectar(("ident", self.acceso(elem.operando)), ("name", u, "operand"))
            self.conectar(entrada, ("name", u, "in"))
            return ("name", u, "out")

        if isinstance(elem, Bobina):
            if elem.tipo not in ("Coil", "SCoil", "RCoil"):
                raise ValueError(f"Tipo de bobina no soportado: {elem.tipo}")
            u = self.uid()
            self.piezas.append(f'<Part Name="{elem.tipo}" UId="{u}" />')
            self.conectar(("ident", self.acceso(elem.operando)), ("name", u, "operand"))
            self.conectar(entrada, ("name", u, "in"))
            return None  # una bobina cierra el escalón

        if isinstance(elem, Serie):
            pin = entrada
            for i, e in enumerate(elem.elementos):
                if pin is None:
                    raise ValueError("Hay elementos después de una bobina en la misma Serie")
                pin = self.emitir(e, pin)
            return pin

        if isinstance(elem, Paralelo):
            salidas = [self.emitir(rama, entrada) for rama in elem.ramas]
            if any(s is None for s in salidas):
                raise ValueError("Las ramas de un Paralelo no pueden terminar en bobina")
            u = self.uid()
            self.piezas.append(
                f'<Part Name="O" UId="{u}">'
                f'<TemplateValue Name="Card" Type="Cardinality">{len(salidas)}</TemplateValue>'
                f"</Part>"
            )
            for i, s in enumerate(salidas, start=1):
                self.conectar(s, ("name", u, f"in{i}"))
            return ("name", u, "out")

        if isinstance(elem, LlamadaFB):
            u = self.uid()
            ui = self.uid()
            params = "".join(
                f"<Parameter Name={quoteattr(n)} Section={quoteattr(p.seccion)} Type={quoteattr(p.tipo)} />"
                for n, p in elem.parametros.items()
            )
            self.piezas.append(
                f'<Call UId="{u}"><CallInfo Name={quoteattr(elem.fb)} BlockType="FB">'
                f'<Instance Scope="GlobalVariable" UId="{ui}">'
                f"<Component Name={quoteattr(elem.instancia)} /></Instance>"
                f"{params}</CallInfo></Call>"
            )
            self.conectar(entrada, ("name", u, "en"))
            for n, p in elem.parametros.items():
                a = self.acceso(p.operando)
                if p.seccion == "Output":
                    self.conectar(("name", u, n), ("ident", a))
                else:
                    self.conectar(("ident", a), ("name", u, n))
            return ("name", u, "eno")

        raise TypeError(f"Elemento KOP desconocido: {elem!r}")

    @staticmethod
    def _con(c) -> str:
        if c[0] == "powerrail":
            return "<Powerrail />"
        if c[0] == "ident":
            return f'<IdentCon UId="{c[1]}" />'
        return f'<NameCon UId="{c[1]}" Name="{c[2]}" />'

    def xml(self, ns_flgnet: str) -> str:
        cables = []
        for origen, destinos in self.cables.items():
            u = self.uid()
            cables.append(f'<Wire UId="{u}">' + self._con(origen)
                          + "".join(self._con(d) for d in destinos) + "</Wire>")
        return (f'<FlgNet xmlns="{ns_flgnet}"><Parts>'
                + "".join(self.accesos) + "".join(self.piezas)
                + "</Parts><Wires>" + "".join(cables) + "</Wires></FlgNet>")


def flgnet(logica, ns_flgnet: str = NS_FLGNET_V17) -> str:
    """Genera solo el <FlgNet> de un escalón (útil para pruebas)."""
    r = _Red()
    r.emitir(logica, POWERRAIL)
    return r.xml(ns_flgnet)


# --------------------------------------------------------------------------
# Documento SimaticML completo
# --------------------------------------------------------------------------
class _Ids:
    def __init__(self):
        self.n = -1

    def __call__(self) -> str:
        self.n += 1
        return format(self.n, "X")  # TIA usa IDs hexadecimales


def _texto_multilingue(ids: _Ids, composicion: str, texto: str, cultura: str) -> str:
    return (
        f'<MultilingualText ID="{ids()}" CompositionName="{composicion}"><ObjectList>'
        f'<MultilingualTextItem ID="{ids()}" CompositionName="Items"><AttributeList>'
        f"<Culture>{cultura}</Culture><Text>{escape(texto)}</Text>"
        f"</AttributeList></MultilingualTextItem></ObjectList></MultilingualText>"
    )


def _miembro(v: Variable, cultura: str, informativo: bool = False) -> str:
    extra = ' Informative="true"' if informativo else ""
    com = (f'<Comment><MultiLanguageText Lang="{cultura}">{escape(v.comentario)}'
           f"</MultiLanguageText></Comment>") if v.comentario else ""
    return f"<Member Name={quoteattr(v.nombre)} Datatype={quoteattr(v.tipo)}{extra}>{com}</Member>" \
        if com else f"<Member Name={quoteattr(v.nombre)} Datatype={quoteattr(v.tipo)}{extra} />"


def _secciones(secciones: dict[str, list], cultura: str, ns_interfaz: str,
               informativo: bool = False) -> str:
    partes = []
    for nombre, variables in secciones.items():
        if variables:
            partes.append(f'<Section Name="{nombre}">'
                          + "".join(_miembro(v, cultura, informativo) for v in variables)
                          + "</Section>")
        else:
            partes.append(f'<Section Name="{nombre}" />')
    return f'<Sections xmlns="{ns_interfaz}">' + "".join(partes) + "</Sections>"


def _unidades(ids: _Ids, redes: list[Red], cultura: str, ns_flgnet: str) -> str:
    out = []
    for red in redes:
        out.append(
            f'<SW.Blocks.CompileUnit ID="{ids()}" CompositionName="CompileUnits">'
            f"<AttributeList><NetworkSource>{flgnet(red.logica, ns_flgnet)}</NetworkSource>"
            f"<ProgrammingLanguage>LAD</ProgrammingLanguage></AttributeList><ObjectList>"
            + _texto_multilingue(ids, "Comment", red.comentario, cultura)
            + _texto_multilingue(ids, "Title", red.titulo, cultura)
            + "</ObjectList></SW.Blocks.CompileUnit>"
        )
    return "".join(out)


def _documento(tipo_xml: str, atributos: str, cuerpo: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<Document>\n"
        '  <Engineering version="V17" />\n'
        f'  <{tipo_xml} ID="0">\n'
        f"    <AttributeList>{atributos}</AttributeList>\n"
        f"    <ObjectList>{cuerpo}</ObjectList>\n"
        f"  </{tipo_xml}>\n"
        "</Document>\n"
    )


def bloque_fb(nombre: str, numero: int, redes: list[Red], *,
              entradas=(), salidas=(), inout=(), estaticas=(), temporales=(),
              titulo: str = "", comentario: str = "", cultura: str = "es-ES",
              ns_interfaz: str = NS_INTERFAZ_V17, ns_flgnet: str = NS_FLGNET_V17) -> str:
    """XML de un FB en KOP con DB de instancia optimizado."""
    ids = _Ids()
    ids()  # el ID 0 es el propio bloque
    secciones = _secciones({"Input": list(entradas), "Output": list(salidas),
                            "InOut": list(inout), "Static": list(estaticas),
                            "Temp": list(temporales), "Constant": []},
                           cultura, ns_interfaz)
    atributos = (f"<Interface>{secciones}</Interface>"
                 "<MemoryLayout>Optimized</MemoryLayout>"
                 f"<Name>{escape(nombre)}</Name><Number>{numero}</Number>"
                 "<ProgrammingLanguage>LAD</ProgrammingLanguage>")
    cuerpo = (_texto_multilingue(ids, "Comment", comentario, cultura)
              + _unidades(ids, redes, cultura, ns_flgnet)
              + _texto_multilingue(ids, "Title", titulo, cultura))
    return _documento("SW.Blocks.FB", atributos, cuerpo)


def bloque_ob1(redes: list[Red], *, nombre: str = "Main", titulo: str = "",
               comentario: str = "", cultura: str = "es-ES",
               ns_interfaz: str = NS_INTERFAZ_V17, ns_flgnet: str = NS_FLGNET_V17) -> str:
    """XML del OB1 (ciclo de programa) en KOP."""
    ids = _Ids()
    ids()
    entradas_ob = [Variable("Initial_Call", "Bool", "Initial call of this OB"),
                   Variable("Remanence", "Bool", "=True, if remanent data are available")]
    secciones = _secciones({"Input": entradas_ob}, "en-US", ns_interfaz, informativo=True)
    # Temp y Constant vacías
    secciones = secciones.replace("</Sections>",
                                  '<Section Name="Temp" /><Section Name="Constant" /></Sections>')
    atributos = (f"<Interface>{secciones}</Interface>"
                 "<MemoryLayout>Optimized</MemoryLayout>"
                 f"<Name>{escape(nombre)}</Name><Number>1</Number>"
                 "<ProgrammingLanguage>LAD</ProgrammingLanguage>"
                 "<SecondaryType>ProgramCycle</SecondaryType>")
    cuerpo = (_texto_multilingue(ids, "Comment", comentario, cultura)
              + _unidades(ids, redes, cultura, ns_flgnet)
              + _texto_multilingue(ids, "Title", titulo, cultura))
    return _documento("SW.Blocks.OB", atributos, cuerpo)
