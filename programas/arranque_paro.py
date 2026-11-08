"""
Programa: Arranque y paro de un motor con retención (enclavamiento).

Cableado (S7-1214C DC/DC/DC):
    I0.0  Marcha       Pulsador de marcha, contacto NA (verde)
    I0.1  Paro_NC      Pulsador de paro, contacto NC (rojo)
    I0.2  Termico_NC   Contacto auxiliar NC del relé térmico (95-96)
    Q0.0  Motor        Bobina del contactor KM1

Los dispositivos de seguridad (paro y térmico) se cablean NC: si un cable se
corta, la entrada cae a 0 y el motor se detiene (falla segura). Por eso en el
programa se usan como contactos NA: "Paro_NC" vale 1 mientras NO se pulsa.
"""
from tia.ladder import (
    Bobina, Contacto, G, L, LlamadaFB, Param, Paralelo, Red, Serie, Variable,
    bloque_fb, bloque_ob1,
)

TABLA_TAGS = "Tags_Motor"
TAGS = [
    # nombre        tipo    dirección  comentario
    ("Marcha",     "Bool", "%I0.0", "Pulsador de marcha (NA)"),
    ("Paro_NC",    "Bool", "%I0.1", "Pulsador de paro (NC) - 1 = no pulsado"),
    ("Termico_NC", "Bool", "%I0.2", "Relé térmico 95-96 (NC) - 1 = sin falla"),
    ("Motor",      "Bool", "%Q0.0", "Contactor KM1 del motor"),
]

FB_NOMBRE = "FB_ArranqueParo"
FB_NUMERO = 1
DB_INSTANCIA = "DB_ArranqueParo"


def xml_fb(cultura="es-ES", **ns) -> str:
    red_retencion = Red(
        titulo="Arranque y paro con retención",
        comentario=("Marcha arranca el motor y el propio contacto de Motor lo mantiene "
                    "(retención). Paro o falla del térmico lo detienen. Paro dominante."),
        logica=Serie(
            Paralelo(Contacto(L("Marcha")), Contacto(L("Motor"))),
            Contacto(L("Paro_NC")),
            Contacto(L("Termico_NC")),
            Bobina(L("Motor")),
        ),
    )
    return bloque_fb(
        FB_NOMBRE, FB_NUMERO, [red_retencion],
        entradas=[Variable("Marcha", "Bool", "Pulsador de marcha (NA)"),
                  Variable("Paro_NC", "Bool", "Pulsador de paro (NC)"),
                  Variable("Termico_NC", "Bool", "Relé térmico (NC)")],
        salidas=[Variable("Motor", "Bool", "Orden al contactor del motor")],
        titulo="Arranque y paro de motor",
        comentario="Generado automáticamente con Claude Code + TIA Openness",
        cultura=cultura, **ns,
    )


def xml_ob1(cultura="es-ES", **ns) -> str:
    red_llamada = Red(
        titulo="Motor 1",
        comentario="Llamada al bloque de arranque y paro con las entradas/salidas físicas",
        logica=LlamadaFB(FB_NOMBRE, DB_INSTANCIA, {
            "Marcha":     Param("Input",  G("Marcha")),
            "Paro_NC":    Param("Input",  G("Paro_NC")),
            "Termico_NC": Param("Input",  G("Termico_NC")),
            "Motor":      Param("Output", G("Motor")),
        }),
    )
    return bloque_ob1([red_llamada], titulo="Programa principal",
                      comentario="Generado automáticamente con Claude Code + TIA Openness",
                      cultura=cultura, **ns)
