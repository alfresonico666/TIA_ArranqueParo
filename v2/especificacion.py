"""Arranque y paro v2 — especificación completa (PLC + HMI KTP400) para generar con TIA_MCP_V17.

Estructura y lógica: patrones probados del equipo (OB1 "director" en KOP que llama a un bloque por
función, banderas S/R, reset manteniendo el botón 3 s, navegación por columna izquierda).
Aspecto de la HMI: fondo negro, botón de navegación activo amarillo, inactivos gris oscuro, panel claro.

Tres estilos de programación del MISMO arranque y paro, ejecutándose a la vez; el selector de la HMI
elige cuál maneja las salidas reales:
  1 Banderas  (KOP, S/R)       : retención con bandera; sin térmico se para y vuelve a arrancar sin RESET.
  2 Moore     (KOP, estados)   : salidas solo según el estado; la falla queda enclavada hasta RESET.
  3 Mealy     (SCL, estados)   : salidas según estado + entradas; el motor cae en el mismo ciclo del paro.
"""
from __future__ import annotations

PROYECTO = "ArranqueParo_v2"
CPU = "6ES7 214-1BG40-0XB0/V4.5"          # S7-1214C AC/DC/RLY
PANEL = "6AV2 123-2GB03-0AX0/17.0.0.0"    # KTP700 Basic PN (800x480)
IP_PLC, IP_HMI = "192.168.0.1", "192.168.0.2"
CONEXION_HMI = "HMI_Connection_1"
CARPETA_BLOQUES = "Motores/ArranqueParo"

# --------------------------------------------------------------------------- tablas de tags (estándar)
TABLAS_TAGS = {
    "Pulsadores_y_selectores": [
        # Memorias (%M) para simular sin PLC ni sensores físicos
        {"nombre": "PB_Marcha", "direccion": "%M10.0", "comentario": "Pulsador MARCHA verde (NA)"},
        {"nombre": "PB_Paro", "direccion": "%M10.1", "comentario": "Pulsador PARO rojo: 1 = pulsado"},
    ],
    "Motores": [
        {"nombre": "MOT1_Termico_Falla", "direccion": "%M10.2", "comentario": "Relé térmico M1: 1 = disparado"},
        {"nombre": "KM1_Motor", "direccion": "%M10.3", "comentario": "Contactor KM1 del motor M1"},
    ],
    "Pilotos": [
        {"nombre": "HL_Marcha", "direccion": "%M10.4", "comentario": "Piloto verde: motor en marcha"},
        {"nombre": "HL_Falla", "direccion": "%M10.5", "comentario": "Piloto rojo: falla térmico"},
    ],
}

# --------------------------------------------------------------------------- DB de HMI (patrón HMI_DATA)
DB_HMI = '''DATA_BLOCK "DB_HMI"
{ S7_Optimized_Access := 'TRUE' }
VERSION : 0.1
NON_RETAIN
   VAR
      Cmd_Marcha : Bool;   // Boton MARCHA de la HMI (momentaneo)
      Cmd_Paro : Bool;   // Boton PARO de la HMI (momentaneo)
      Cmd_Reset : Bool;   // Boton RESET de la HMI (momentaneo)
      Sel_Estilo : Int := 1;   // 1 Banderas, 2 Moore, 3 Mealy
      Estado : Int;   // Estado del estilo seleccionado: 0 Reposo, 10 Marcha, 90 Falla
      Motor_En_Marcha : Bool;   // Copia de KM1_Motor para la HMI
      Falla_Termico : Bool;   // Termico disparado
      Pantalla : Int;   // Pantalla activa en la HMI (1 Principal, 2 Diagnostico, 3 Estilos)
   END_VAR

BEGIN
   Sel_Estilo := 1;
END_DATA_BLOCK
'''

# --------------------------------------------------------------------------- interfaz común de los 3 estilos
_ENTRADAS = [{"nombre": "Marcha", "comentario": "Orden de marcha (pulsador o HMI)"},
             {"nombre": "Paro", "comentario": "Orden de paro: 1 = parar"},
             {"nombre": "Termico_OK", "comentario": "1 = relé térmico sin falla"},
             {"nombre": "Reset", "comentario": "Reset de falla"}]
_SALIDAS = [{"nombre": "Motor", "comentario": "Orden al contactor"},
            {"nombre": "Piloto_Marcha", "comentario": "Piloto verde"},
            {"nombre": "Piloto_Falla", "comentario": "Piloto rojo"}]

# --------------------------------------------------------------------------- mando: pulsadores + HMI
FB_MANDO = {
    "tipo": "FB", "nombre": "FB_Mando_Motor", "titulo": "Mando del motor: pulsadores + HMI",
    "comentario": "Une pulsadores físicos y botones HMI. Reset = botón RESET de la HMI o mantener MARCHA 3 s.",
    "interfaz": {
        "Input": [{"nombre": "PB_Marcha", "comentario": "Pulsador MARCHA (NA)"},
                  {"nombre": "PB_Paro", "comentario": "Pulsador PARO: 1 = pulsado"},
                  {"nombre": "Termico_Falla", "comentario": "Relé térmico: 1 = disparado"},
                  {"nombre": "HMI_Marcha"}, {"nombre": "HMI_Paro"}, {"nombre": "HMI_Reset"}],
        "Output": [{"nombre": "Marcha"}, {"nombre": "Paro"}, {"nombre": "Termico_OK"}, {"nombre": "Reset"}],
        "Static": [{"nombre": "T_Reset", "tipo": "TON_TIME", "comentario": "Tiempo de MARCHA mantenida"},
                   {"nombre": "Reset_Mantenido", "comentario": "MARCHA mantenida 3 s"}],
    },
    "redes": [
        {"titulo": "Marcha", "comentario": "Pulsador físico o botón de la HMI.",
         "logica": [{"paralelo": [{"contacto": "#PB_Marcha"}, {"contacto": "#HMI_Marcha"}]},
                    {"bobina": "#Marcha"}]},
        {"titulo": "Paro", "comentario": "Pulsador PARO o botón PARO de la HMI.",
         "logica": [{"paralelo": [{"contacto": "#PB_Paro"}, {"contacto": "#HMI_Paro"}]},
                    {"bobina": "#Paro"}]},
        {"titulo": "Térmico", "comentario": "Térmico OK mientras no esté disparado.",
         "logica": [{"contacto": "#Termico_Falla", "negado": True}, {"bobina": "#Termico_OK"}]},
        {"titulo": "MARCHA mantenida 3 s", "comentario": "Patrón de reset probado: mantener el pulsador 3 s.",
         "logica": [{"contacto": "#PB_Marcha"},
                    {"caja": "TON", "instancia": "#T_Reset", "entradas": {"PT": "T#3s"}},
                    {"bobina": "#Reset_Mantenido"}]},
        {"titulo": "Reset", "comentario": "Botón RESET de la HMI o MARCHA mantenida 3 s.",
         "logica": [{"paralelo": [{"contacto": "#Reset_Mantenido"}, {"contacto": "#HMI_Reset"}]},
                    {"bobina": "#Reset"}]},
    ],
}

# --------------------------------------------------------------------------- estilo 1: banderas (S/R)
FB_BANDERAS = {
    "tipo": "FB", "nombre": "FB_Motor_Banderas", "titulo": "Arranque y paro por BANDERAS (S/R)",
    "comentario": "Estilo clásico: bandera de marcha con SET/RESET (paro dominante). Sin térmico se para; "
                  "al recuperarse el térmico se puede volver a arrancar sin RESET.",
    "interfaz": {
        "Input": _ENTRADAS,
        "Output": [*_SALIDAS, {"nombre": "Estado", "tipo": "Int", "comentario": "0 Reposo, 10 Marcha, 90 Falla"}],
        "Static": [{"nombre": "B_Marcha", "comentario": "Bandera: motor en marcha"},
                   {"nombre": "B_Falla", "comentario": "Bandera: falla térmico"}],
    },
    "redes": [
        {"titulo": "SET bandera de marcha", "comentario": "Marcha sin paro y con térmico OK.",
         "logica": [{"contacto": "#Marcha"}, {"contacto": "#Paro", "negado": True}, {"contacto": "#Termico_OK"},
                    {"set": "#B_Marcha"}]},
        {"titulo": "RESET bandera de marcha", "comentario": "Paro o falla. Va después del SET: paro dominante.",
         "logica": [{"paralelo": [{"contacto": "#Paro"}, {"contacto": "#Termico_OK", "negado": True}]},
                    {"reset": "#B_Marcha"}]},
        {"titulo": "Bandera de falla", "comentario": "Sigue al térmico (no queda enclavada).",
         "logica": [{"contacto": "#Termico_OK", "negado": True}, {"bobina": "#B_Falla"}]},
        {"titulo": "Salidas", "comentario": "Motor y pilotos según las banderas.",
         "logica": [{"contacto": "#B_Marcha"}, {"bobina": "#Motor"}]},
        {"titulo": "Piloto de marcha", "logica": [{"contacto": "#B_Marcha"}, {"bobina": "#Piloto_Marcha"}]},
        {"titulo": "Piloto de falla", "logica": [{"contacto": "#B_Falla"}, {"bobina": "#Piloto_Falla"}]},
        {"titulo": "Estado para HMI", "comentario": "Equivalente a los estados de Moore/Mealy para comparar.",
         "logica": [{"contacto": "#B_Marcha", "negado": True}, {"contacto": "#B_Falla", "negado": True},
                    {"caja": "MOVE", "entradas": {"in": "0"}, "salidas": {"out1": "#Estado"}}]},
        {"titulo": "Estado = 10 (marcha)",
         "logica": [{"contacto": "#B_Marcha"},
                    {"caja": "MOVE", "entradas": {"in": "10"}, "salidas": {"out1": "#Estado"}}]},
        {"titulo": "Estado = 90 (falla)",
         "logica": [{"contacto": "#B_Falla"},
                    {"caja": "MOVE", "entradas": {"in": "90"}, "salidas": {"out1": "#Estado"}}]},
    ],
}

# --------------------------------------------------------------------------- estilos 2 y 3: máquinas de estados
_ESTADOS_MOORE = [
    {"nombre": "REPOSO", "valor": 0},
    {"nombre": "MARCHA", "valor": 10, "salidas": {"Motor": True, "Piloto_Marcha": True}},
    {"nombre": "FALLA", "valor": 90, "salidas": {"Piloto_Falla": True}},
]
_TRANSICIONES = [
    {"desde": "*", "hacia": "FALLA", "si": ["NOT Termico_OK"]},
    {"desde": "REPOSO", "hacia": "MARCHA", "si": ["Marcha", "NOT Paro", "Termico_OK"]},
    {"desde": "MARCHA", "hacia": "REPOSO", "si": ["Paro"]},
    {"desde": "FALLA", "hacia": "REPOSO", "si": ["Reset", "Termico_OK"]},
]
MAQUINA_MOORE = {
    "nombre": "FB_Motor_Moore", "estilo": "moore", "lenguaje": "kop",
    "titulo": "Arranque y paro: máquina de estados MOORE",
    "entradas": _ENTRADAS, "salidas": _SALIDAS, "inicial": "REPOSO",
    "estados": _ESTADOS_MOORE, "transiciones": _TRANSICIONES,
}
MAQUINA_MEALY = {
    "nombre": "FB_Motor_Mealy", "estilo": "mealy", "lenguaje": "scl",
    "titulo": "Arranque y paro: maquina de estados MEALY",
    "entradas": _ENTRADAS, "salidas": _SALIDAS, "inicial": "REPOSO",
    "estados": [
        {"nombre": "REPOSO", "valor": 0},
        # Mealy: el motor depende del estado Y de las entradas -> cae en el mismo ciclo del paro/falla
        {"nombre": "MARCHA", "valor": 10, "salidas": {"Motor": ["NOT Paro", "Termico_OK"], "Piloto_Marcha": True}},
        {"nombre": "FALLA", "valor": 90, "salidas": {"Piloto_Falla": True}},
    ],
    "transiciones": _TRANSICIONES,
}

INSTANCIAS = {"DB_Mando": "FB_Mando_Motor", "DB_Motor_Banderas": "FB_Motor_Banderas",
              "DB_Motor_Moore": "FB_Motor_Moore", "DB_Motor_Mealy": "FB_Motor_Mealy"}


# --------------------------------------------------------------------------- OB1 director
def _por_estilo(miembro: str) -> dict:
    """OR de (Sel_Estilo == n AND "DB_Motor_<estilo>".<miembro>) para los 3 estilos."""
    return {"paralelo": [
        {"serie": [{"comparar": ['"DB_HMI".Sel_Estilo', "==", str(n)], "tipo": "Int"},
                   {"contacto": f'"{db}".{miembro}'}]}
        for n, db in ((1, "DB_Motor_Banderas"), (2, "DB_Motor_Moore"), (3, "DB_Motor_Mealy"))]}


def _llamada_estilo(fb: str, db: str) -> dict:
    return {"llamar": fb, "instancia": db, "parametros": {
        "Marcha": '"DB_Mando".Marcha', "Paro": '"DB_Mando".Paro',
        "Termico_OK": '"DB_Mando".Termico_OK', "Reset": '"DB_Mando".Reset'}}


MAIN = {
    "tipo": "OB", "nombre": "Main", "numero": 1, "titulo": "Programa principal - Arranque y paro v2",
    "comentario": "OB1 director: una red por función. Los 3 estilos corren a la vez; el selector de la HMI "
                  "decide cuál maneja KM1 y los pilotos.",
    "redes": [
        {"titulo": "MANDO: pulsadores + HMI", "comentario": "Une entradas físicas y botones de la HMI.",
         "logica": {"llamar": "FB_Mando_Motor", "instancia": "DB_Mando", "parametros": {
             "PB_Marcha": '"PB_Marcha"', "PB_Paro": '"PB_Paro"', "Termico_Falla": '"MOT1_Termico_Falla"',
             "HMI_Marcha": '"DB_HMI".Cmd_Marcha', "HMI_Paro": '"DB_HMI".Cmd_Paro',
             "HMI_Reset": '"DB_HMI".Cmd_Reset'}}},
        {"titulo": "ESTILO 1: BANDERAS (S/R)", "logica": _llamada_estilo("FB_Motor_Banderas", "DB_Motor_Banderas")},
        {"titulo": "ESTILO 2: MOORE (estados, KOP)", "logica": _llamada_estilo("FB_Motor_Moore", "DB_Motor_Moore")},
        {"titulo": "ESTILO 3: MEALY (estados, SCL)", "logica": _llamada_estilo("FB_Motor_Mealy", "DB_Motor_Mealy")},
        {"titulo": "SALIDA: contactor KM1 según estilo", "comentario": "Solo el estilo elegido en la HMI manda.",
         "logica": [_por_estilo("Motor"), {"bobina": '"KM1_Motor"'}]},
        {"titulo": "SALIDA: piloto de marcha", "logica": [_por_estilo("Piloto_Marcha"), {"bobina": '"HL_Marcha"'}]},
        {"titulo": "SALIDA: piloto de falla", "logica": [_por_estilo("Piloto_Falla"), {"bobina": '"HL_Falla"'}]},
        {"titulo": "HMI: motor en marcha", "logica": [{"contacto": '"KM1_Motor"'},
                                                      {"bobina": '"DB_HMI".Motor_En_Marcha'}]},
        {"titulo": "HMI: falla térmico", "logica": [{"contacto": '"MOT1_Termico_Falla"'},
                                                    {"bobina": '"DB_HMI".Falla_Termico'}]},
        *[{"titulo": f"HMI: estado del estilo {n}",
           "logica": [{"comparar": ['"DB_HMI".Sel_Estilo', "==", str(n)], "tipo": "Int"},
                      {"caja": "MOVE", "entradas": {"in": f'"{db}".Estado'},
                       "salidas": {"out1": '"DB_HMI".Estado'}}]}
          for n, db in ((1, "DB_Motor_Banderas"), (2, "DB_Motor_Moore"), (3, "DB_Motor_Mealy"))],
    ],
}

# --------------------------------------------------------------------------- HMI: tags, listas, pantallas
TAGS_HMI = [
    # nombre HMI, tipo, tag PLC
    ("Cmd_Marcha", "Bool", "DB_HMI.Cmd_Marcha"), ("Cmd_Paro", "Bool", "DB_HMI.Cmd_Paro"),
    ("Cmd_Reset", "Bool", "DB_HMI.Cmd_Reset"), ("Sel_Estilo", "Int", "DB_HMI.Sel_Estilo"),
    ("Estado", "Int", "DB_HMI.Estado"), ("Motor_En_Marcha", "Bool", "DB_HMI.Motor_En_Marcha"),
    ("Falla_Termico", "Bool", "DB_HMI.Falla_Termico"), ("Pantalla", "Int", "DB_HMI.Pantalla"),
    ("PB_Marcha", "Bool", "PB_Marcha"), ("PB_Paro", "Bool", "PB_Paro"),
    ("MOT1_Termico_Falla", "Bool", "MOT1_Termico_Falla"), ("KM1_Motor", "Bool", "KM1_Motor"),
    ("HL_Marcha", "Bool", "HL_Marcha"), ("HL_Falla", "Bool", "HL_Falla"),
    ("Banderas_Estado", "Int", "DB_Motor_Banderas.Estado"), ("Banderas_Motor", "Bool", "DB_Motor_Banderas.Motor"),
    ("Moore_Estado", "Int", "DB_Motor_Moore.Estado"), ("Moore_Motor", "Bool", "DB_Motor_Moore.Motor"),
    ("Mealy_Estado", "Int", "DB_Motor_Mealy.Estado"), ("Mealy_Motor", "Bool", "DB_Motor_Mealy.Motor"),
]
TABLA_TAGS_HMI = "HMI_Motor"
LISTAS = {"Estilos": {1: "BANDERAS", 2: "MOORE", 3: "MEALY"},
          "Estados": {0: "REPOSO", 10: "MARCHA", 90: "FALLA"}}

# Paleta (aspecto de la HMI de referencia del equipo: negro + amarillo, Tahoma)
NEGRO, AMARILLO, GRIS_OSCURO = "0, 0, 0", "255, 203, 0", "51, 51, 51"
PANEL_CLARO, BORDE, TEXTO_OSCURO, BLANCO = "238, 238, 241", "24, 28, 49", "49, 52, 74", "255, 255, 255"
VERDE, ROJO, APAGADO = "0, 200, 0", "220, 0, 0", "150, 150, 150"
TARJETA, BORDE_TARJETA, GRIS_TEXTO = "255, 255, 255", "205, 205, 212", "110, 112, 125"
ANCHO, ALTO = 800, 480                     # KTP700 Basic
X0 = 180                                   # inicio del contenido (a la derecha de la navegación)
PANTALLAS_NAV = [("Principal", "PRINCIPAL", 1), ("Diagnostico", "DIAGNÓSTICO", 2), ("Estilos", "ESTILOS", 3)]


def _etiqueta(nombre, x, y, ancho, texto, tamano=13, color=TEXTO_OSCURO, estilo="Bold", alto=24,
              alineacion="izquierda"):
    return {"tipo": "texto", "nombre": nombre, "x": x, "y": y, "ancho": ancho, "alto": alto, "texto": texto,
            "fuente": {"tamano": tamano, "estilo": estilo}, "color": color, "transparente": True,
            "alineacion": alineacion}


def _tarjeta(nombre, x, y, ancho, alto, titulo=None):
    objetos = [{"tipo": "rectangulo", "nombre": nombre, "x": x, "y": y, "ancho": ancho, "alto": alto,
                "fondo": TARJETA, "borde": BORDE_TARJETA, "grosor_borde": 1, "radio_esquina": 12}]
    if titulo:
        objetos += [_etiqueta(f"{nombre}_Titulo", x + 14, y + 8, ancho - 28, titulo, 12, GRIS_TEXTO),
                    {"tipo": "linea", "nombre": f"{nombre}_Linea", "x1": x + 14, "y1": y + 34, "x2": x + ancho - 14,
                     "y2": y + 34, "color": AMARILLO, "grosor": 2}]
    return objetos


def _led(nombre, x, y, diametro, tag, color_on, borde=BORDE, grosor=1):
    return {"tipo": "circulo", "nombre": nombre, "x": x, "y": y, "ancho": diametro, "alto": diametro,
            "borde": borde, "grosor_borde": grosor,
            "apariencia": {"tag": tag, "rangos": [[0, APAGADO], [1, color_on]]}}


def _cabecera(titulo: str) -> list[dict]:
    """Barra superior negra: título blanco, fecha/hora a la derecha y línea amarilla."""
    return [
        _etiqueta("Titulo", X0, 6, 430, titulo, 24, BLANCO, "Bold", 48),
        {"tipo": "fecha_hora", "nombre": "Fecha", "x": 620, "y": 8, "ancho": 170, "alto": 22, "fecha": True,
         "hora": False, "color": BLANCO, "alineacion": "derecha", "fuente": {"tamano": 12, "estilo": "Bold"}},
        {"tipo": "fecha_hora", "nombre": "Hora", "x": 620, "y": 30, "ancho": 170, "alto": 22, "fecha": False,
         "hora": True, "color": AMARILLO, "alineacion": "derecha", "fuente": {"tamano": 14, "estilo": "Bold"}},
        {"tipo": "linea", "nombre": "Linea_Cabecera", "x1": 0, "y1": 60, "x2": ANCHO, "y2": 60, "color": AMARILLO,
         "grosor": 3},
        _etiqueta("Marca", 14, 14, 150, "M1", 26, AMARILLO, "Bold", 36),
    ]


def _navegacion(activa: str) -> list[dict]:
    """Columna izquierda: activa amarilla, resto gris oscuro; abajo, estado rápido del motor."""
    objetos = []
    for i, (pantalla, texto, numero) in enumerate(PANTALLAS_NAV):
        es_activa = pantalla == activa
        objetos.append({
            "tipo": "boton", "nombre": f"Nav_{pantalla}", "x": 10, "y": 76 + 66 * i, "ancho": 158, "alto": 56,
            "texto": texto, "fondo": AMARILLO if es_activa else GRIS_OSCURO,
            "color": GRIS_OSCURO if es_activa else BLANCO, "borde": BLANCO if es_activa else "120, 120, 120",
            "grosor_borde": 3, "radio_esquina": 10, "fuente": {"tamano": 14, "estilo": "Bold"},
            "al_click": [["ActivateScreen", pantalla], ["SetTag", "Pantalla", numero]]})
    objetos += [
        _led("Nav_Led_Motor", 16, 418, 40, "Motor_En_Marcha", VERDE, AMARILLO, 3),
        _etiqueta("Nav_Txt_Motor", 64, 418, 110, "MOTOR", 13, BLANCO, "Bold", 20),
        _etiqueta("Nav_Txt_KM1", 64, 438, 110, "KM1", 11, "180, 180, 180", "Regular", 20),
    ]
    return objetos


def _fondo_contenido() -> dict:
    return {"tipo": "rectangulo", "nombre": "Contenido", "x": X0, "y": 70, "ancho": ANCHO - X0 - 8,
            "alto": ALTO - 78, "fondo": PANEL_CLARO, "borde": BORDE, "grosor_borde": 1, "radio_esquina": 14}


def _pildora(nombre, x, y, texto, tag, color_on, color_off, color_texto):
    return [{"tipo": "rectangulo", "nombre": f"Ind_{nombre}", "x": x, "y": y, "ancho": 262, "alto": 40,
             "fondo": color_off, "borde": BORDE_TARJETA, "grosor_borde": 1, "radio_esquina": 10,
             "apariencia": {"tag": tag, "rangos": [[0, color_off], [1, color_on]]},
             **({"parpadeo_en": 1} if nombre == "Falla" else {})},
            _etiqueta(f"Txt_{nombre}", x, y + 8, 262, texto, 15, color_texto, alineacion="centro")]


def _boton_mando(nombre, x, texto, tag, fondo, color):
    return {"tipo": "boton", "nombre": nombre, "x": x, "y": 384, "ancho": 184, "alto": 76, "texto": texto,
            "fondo": fondo, "color": color, "borde": BLANCO, "grosor_borde": 3, "radio_esquina": 12,
            "fuente": {"tamano": 20, "estilo": "Bold"},
            "al_pulsar": [["SetBit", tag]], "al_soltar": [["ResetBit", tag]]}


PANTALLA_PRINCIPAL = {
    "nombre": "Principal", "numero": 1, "fondo": NEGRO, "ancho": ANCHO, "alto": ALTO, "objetos": [
        *_cabecera("ARRANQUE Y PARO"), *_navegacion("Principal"), _fondo_contenido(),
        # Tarjeta MOTOR: LED grande con aro amarillo, estado y estilo
        *_tarjeta("Card_Motor", 192, 82, 290, 284, "MOTOR M1"),
        {"tipo": "circulo", "nombre": "Aro_Motor", "x": 262, "y": 124, "ancho": 150, "alto": 150,
         "fondo": GRIS_OSCURO, "borde": AMARILLO, "grosor_borde": 6},
        _led("Led_Motor", 280, 142, 114, "Motor_En_Marcha", VERDE, BORDE, 2),
        _etiqueta("Txt_KM1", 204, 278, 266, "KM1 · M10.3", 12, GRIS_TEXTO, "Regular", 20, "centro"),
        _etiqueta("Txt_Estado", 204, 302, 80, "Estado", 13),
        {"tipo": "campo_simbolico", "nombre": "Estado", "tag": "Estado", "lista": "Estados", "modo": "salida",
         "x": 284, "y": 298, "ancho": 186, "alto": 30, "fuente": {"tamano": 14, "estilo": "Bold"}},
        _etiqueta("Txt_Estilo", 204, 336, 80, "Estilo", 13),
        {"tipo": "campo_simbolico", "nombre": "Sel_Estilo", "tag": "Sel_Estilo", "lista": "Estilos",
         "modo": "entrada_salida", "x": 284, "y": 332, "ancho": 186, "alto": 30,
         "fuente": {"tamano": 14, "estilo": "Bold"}},
        # Tarjeta SEÑALES: MARCHA / PARO / FALLA y pilotos
        *_tarjeta("Card_Senales", 494, 82, 286, 284, "SEÑALES"),
        *_pildora("Marcha", 506, 126, "EN MARCHA", "Motor_En_Marcha", VERDE, APAGADO, BLANCO),
        *_pildora("Paro", 506, 174, "PARADO", "Motor_En_Marcha", APAGADO, ROJO, BLANCO),
        *_pildora("Falla", 506, 222, "FALLA TÉRMICO", "Falla_Termico", AMARILLO, APAGADO, GRIS_OSCURO),
        _led("Led_HL_Marcha", 514, 280, 30, "HL_Marcha", VERDE),
        _etiqueta("Txt_HL_Marcha", 552, 284, 220, "Piloto marcha  M10.4", 12, TEXTO_OSCURO, "Regular", 22),
        _led("Led_HL_Falla", 514, 322, 30, "HL_Falla", ROJO),
        _etiqueta("Txt_HL_Falla", 552, 326, 220, "Piloto falla  M10.5", 12, TEXTO_OSCURO, "Regular", 22),
        # MANDO
        _boton_mando("Btn_Marcha", 196, "MARCHA", "Cmd_Marcha", "0, 160, 0", BLANCO),
        _boton_mando("Btn_Paro", 394, "PARO", "Cmd_Paro", "200, 0, 0", BLANCO),
        _boton_mando("Btn_Reset", 592, "RESET", "Cmd_Reset", AMARILLO, GRIS_OSCURO),
    ]}

# (tag, dirección, texto, color cuando vale 1)
_ENTRADAS_IO = [("PB_Marcha", "M10.0", "Pulsador MARCHA", VERDE), ("PB_Paro", "M10.1", "Pulsador PARO", ROJO),
                ("MOT1_Termico_Falla", "M10.2", "Térmico M1 disparado", ROJO)]
_SALIDAS_IO = [("KM1_Motor", "M10.3", "Contactor KM1", VERDE), ("HL_Marcha", "M10.4", "Piloto marcha", VERDE),
               ("HL_Falla", "M10.5", "Piloto falla", ROJO)]


def _filas_io(filas, x):
    objetos = []
    for i, (tag, direccion, texto, color) in enumerate(filas):
        y = 140 + 92 * i
        objetos += [
            {"tipo": "rectangulo", "nombre": f"Fila_{tag}", "x": x + 10, "y": y - 10, "ancho": 266, "alto": 76,
             "fondo": "246, 246, 248", "borde": BORDE_TARJETA, "grosor_borde": 1, "radio_esquina": 10},
            _led(f"Led_{tag}", x + 24, y + 6, 44, tag, color),
            _etiqueta(f"Dir_{tag}", x + 82, y + 2, 180, direccion, 18, TEXTO_OSCURO, "Bold", 28),
            _etiqueta(f"Des_{tag}", x + 82, y + 30, 186, texto, 12, GRIS_TEXTO, "Regular", 22),
        ]
    return objetos


PANTALLA_DIAGNOSTICO = {
    "nombre": "Diagnostico", "numero": 2, "fondo": NEGRO, "ancho": ANCHO, "alto": ALTO, "objetos": [
        *_cabecera("DIAGNÓSTICO"), *_navegacion("Diagnostico"), _fondo_contenido(),
        *_tarjeta("Card_Entradas", 192, 82, 288, 380, "ENTRADAS (memorias)"), *_filas_io(_ENTRADAS_IO, 192),
        *_tarjeta("Card_Salidas", 492, 82, 288, 380, "SALIDAS (memorias)"), *_filas_io(_SALIDAS_IO, 492),
    ]}

_ESTILOS = [("Banderas", 1, "BANDERAS", "KOP · SET/RESET", "Rearranca sin RESET"),
            ("Moore", 2, "MOORE", "KOP · estados", "Falla: requiere RESET"),
            ("Mealy", 3, "MEALY", "SCL · estados", "Para en el mismo ciclo")]


def _tarjeta_estilo(i, clave, numero, titulo, lenguaje, nota):
    x = 192 + 198 * i
    return [
        *_tarjeta(f"Card_{clave}", x, 82, 190, 278),
        {"tipo": "rectangulo", "nombre": f"Activo_{clave}", "x": x, "y": 82, "ancho": 190, "alto": 10,
         "fondo": AMARILLO, "borde": AMARILLO, "grosor_borde": 0, "radio_esquina": 4,
         "visible_si": {"tag": "Sel_Estilo", "desde": numero, "hasta": numero}},
        _etiqueta(f"Tit_{clave}", x, 100, 190, f"{numero}  {titulo}", 18, TEXTO_OSCURO, "Bold", 30, "centro"),
        _etiqueta(f"Len_{clave}", x, 132, 190, lenguaje, 12, GRIS_TEXTO, "Regular", 20, "centro"),
        {"tipo": "circulo", "nombre": f"Aro_{clave}", "x": x + 55, "y": 162, "ancho": 80, "alto": 80,
         "fondo": GRIS_OSCURO, "borde": AMARILLO, "grosor_borde": 4},
        _led(f"Led_{clave}", x + 65, 172, 60, f"{clave}_Motor", VERDE, BORDE, 2),
        {"tipo": "campo_simbolico", "nombre": f"Est_{clave}", "tag": f"{clave}_Estado", "lista": "Estados",
         "modo": "salida", "x": x + 20, "y": 256, "ancho": 150, "alto": 30,
         "fuente": {"tamano": 14, "estilo": "Bold"}},
        _etiqueta(f"Nota_{clave}", x, 300, 190, nota, 11, GRIS_TEXTO, "Italic", 22, "centro"),
    ]


PANTALLA_ESTILOS = {
    "nombre": "Estilos", "numero": 3, "fondo": NEGRO, "ancho": ANCHO, "alto": ALTO, "objetos": [
        *_cabecera("ESTILOS EN PARALELO"), *_navegacion("Estilos"), _fondo_contenido(),
        *[obj for i, e in enumerate(_ESTILOS) for obj in _tarjeta_estilo(i, *e)],
        *_tarjeta("Card_Selector", 192, 372, 588, 88),
        _etiqueta("Txt_Selector", 210, 398, 260, "Estilo que manda KM1:", 16, TEXTO_OSCURO, "Bold", 30),
        {"tipo": "campo_simbolico", "nombre": "Sel_Estilo_2", "tag": "Sel_Estilo", "lista": "Estilos",
         "modo": "entrada_salida", "x": 480, "y": 392, "ancho": 280, "alto": 42,
         "fuente": {"tamano": 18, "estilo": "Bold"}},
    ]}

PANTALLAS = [PANTALLA_PRINCIPAL, PANTALLA_DIAGNOSTICO, PANTALLA_ESTILOS]
