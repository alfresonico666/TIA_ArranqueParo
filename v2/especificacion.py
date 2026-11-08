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
PANEL = "6AV2 123-2DB03-0AX0/17.0.0.0"    # KTP400 Basic PN
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

# Paleta (aspecto de la HMI de referencia del equipo)
NEGRO, AMARILLO, GRIS_OSCURO = "0, 0, 0", "255, 203, 0", "51, 51, 51"
PANEL_CLARO, BORDE, TEXTO_OSCURO, BLANCO = "247, 243, 247", "24, 28, 49", "49, 52, 74", "255, 255, 255"
VERDE, ROJO, APAGADO = "0, 200, 0", "220, 0, 0", "120, 120, 120"
PANTALLAS_NAV = [("Principal", "PRINCIPAL", 1), ("Diagnostico", "DIAGNÓSTICO", 2), ("Estilos", "ESTILOS", 3)]


def _navegacion(activa: str) -> list[dict]:
    """Columna izquierda (x=3, 119x38, paso 43 px): activa amarilla, resto gris oscuro."""
    botones = []
    for i, (pantalla, texto, numero) in enumerate(PANTALLAS_NAV):
        es_activa = pantalla == activa
        botones.append({
            "tipo": "boton", "nombre": f"Nav_{pantalla}", "x": 3, "y": 8 + 43 * i, "ancho": 119, "alto": 38,
            "texto": texto, "fondo": AMARILLO if es_activa else GRIS_OSCURO,
            "color": GRIS_OSCURO if es_activa else BLANCO, "borde": BLANCO if es_activa else "192, 192, 192",
            "grosor_borde": 3, "radio_esquina": 8, "fuente": {"tamano": 13, "estilo": "Bold"},
            "al_click": [["ActivateScreen", pantalla], ["SetTag", "Pantalla", numero]]})
    botones += [
        {"tipo": "fecha_hora", "nombre": "Fecha", "x": 3, "y": 226, "ancho": 119, "alto": 20, "fecha": True,
         "hora": False, "color": BLANCO, "fuente": {"tamano": 11, "estilo": "Bold"}},
        {"tipo": "fecha_hora", "nombre": "Hora", "x": 3, "y": 248, "ancho": 119, "alto": 20, "fecha": False,
         "hora": True, "color": AMARILLO, "fuente": {"tamano": 11, "estilo": "Bold"}}]
    return botones


def _marco(titulo: str) -> list[dict]:
    return [
        {"tipo": "rectangulo", "nombre": "Panel", "x": 127, "y": 0, "ancho": 353, "alto": 272,
         "fondo": PANEL_CLARO, "borde": BORDE, "grosor_borde": 1},
        {"tipo": "texto", "nombre": "Titulo", "x": 133, "y": 0, "ancho": 343, "alto": 42, "texto": titulo,
         "fuente": {"tamano": 22, "estilo": "Bold, Italic"}, "color": TEXTO_OSCURO, "transparente": True},
        {"tipo": "linea", "nombre": "Linea_Titulo", "x1": 137, "y1": 42, "x2": 470, "y2": 42, "color": AMARILLO,
         "grosor": 3}]


def _etiqueta(nombre, x, y, ancho, texto, tamano=13, color=TEXTO_OSCURO, estilo="Bold", alto=24,
              alineacion="izquierda"):
    return {"tipo": "texto", "nombre": nombre, "x": x, "y": y, "ancho": ancho, "alto": alto, "texto": texto,
            "fuente": {"tamano": tamano, "estilo": estilo}, "color": color, "transparente": True,
            "alineacion": alineacion}


def _piloto_rect(nombre, x, y, tag, color_on, ancho=44, alto=26):
    return {"tipo": "rectangulo", "nombre": nombre, "x": x, "y": y, "ancho": ancho, "alto": alto,
            "fondo": APAGADO, "borde": BORDE, "grosor_borde": 1,
            "apariencia": {"tag": tag, "rangos": [[0, APAGADO], [1, color_on]]}}


def _boton_momentaneo(nombre, x, texto, tag, fondo, color):
    return {"tipo": "boton", "nombre": nombre, "x": x, "y": 212, "ancho": 108, "alto": 52, "texto": texto,
            "fondo": fondo, "color": color, "borde": BLANCO, "grosor_borde": 3, "radio_esquina": 8,
            "fuente": {"tamano": 16, "estilo": "Bold"},
            "al_pulsar": [["SetBit", tag]], "al_soltar": [["ResetBit", tag]]}


PANTALLA_PRINCIPAL = {
    "nombre": "Principal", "numero": 1, "fondo": NEGRO, "objetos": [
        *_marco("ARRANQUE Y PARO M1"), *_navegacion("Principal"),
        # Estado de la máquina: MARCHA / PARO / FALLA
        {"tipo": "rectangulo", "nombre": "Ind_Marcha", "x": 137, "y": 50, "ancho": 106, "alto": 30,
         "fondo": APAGADO, "borde": BORDE, "grosor_borde": 1,
         "apariencia": {"tag": "Motor_En_Marcha", "rangos": [[0, APAGADO], [1, VERDE]]}},
        _etiqueta("Txt_Marcha", 137, 53, 106, "MARCHA", 14, BLANCO, alineacion="centro"),
        {"tipo": "rectangulo", "nombre": "Ind_Paro", "x": 250, "y": 50, "ancho": 106, "alto": 30,
         "fondo": APAGADO, "borde": BORDE, "grosor_borde": 1,
         "apariencia": {"tag": "Motor_En_Marcha", "rangos": [[0, ROJO], [1, APAGADO]]}},
        _etiqueta("Txt_Paro", 250, 53, 106, "PARO", 14, BLANCO, alineacion="centro"),
        {"tipo": "rectangulo", "nombre": "Ind_Falla", "x": 363, "y": 50, "ancho": 106, "alto": 30,
         "fondo": APAGADO, "borde": BORDE, "grosor_borde": 1, "parpadeo_en": 1,
         "apariencia": {"tag": "Falla_Termico", "rangos": [[0, APAGADO], [1, AMARILLO]]}},
        _etiqueta("Txt_Falla", 363, 53, 106, "FALLA", 14, GRIS_OSCURO, alineacion="centro"),
        # Motor
        {"tipo": "circulo", "nombre": "Led_Motor", "x": 150, "y": 98, "ancho": 64, "alto": 64,
         "borde": BORDE, "grosor_borde": 2,
         "apariencia": {"tag": "Motor_En_Marcha", "rangos": [[0, GRIS_OSCURO], [1, VERDE]]}},
        _etiqueta("Txt_Motor", 137, 166, 90, "MOTOR M1", 12),
        _etiqueta("Txt_KM1", 137, 184, 90, "KM1 · M10.3", 11, TEXTO_OSCURO, "Regular", 20),
        # Selector de estilo y estado
        _etiqueta("Txt_Estilo", 240, 96, 80, "Estilo:", 14),
        {"tipo": "campo_simbolico", "nombre": "Sel_Estilo", "tag": "Sel_Estilo", "lista": "Estilos",
         "modo": "entrada_salida", "x": 320, "y": 94, "ancho": 150, "alto": 30,
         "fuente": {"tamano": 14, "estilo": "Bold"}},
        _etiqueta("Txt_Estado", 240, 140, 80, "Estado:", 14),
        {"tipo": "campo_simbolico", "nombre": "Estado", "tag": "Estado", "lista": "Estados", "modo": "salida",
         "x": 320, "y": 138, "ancho": 150, "alto": 30, "fuente": {"tamano": 14, "estilo": "Bold"}},
        _etiqueta("Txt_Ayuda", 240, 174, 235, "RESET: botón o MARCHA 3 s", 11, TEXTO_OSCURO, "Italic", 20),
        # Botones de mando
        _boton_momentaneo("Btn_Marcha", 137, "MARCHA", "Cmd_Marcha", "0, 160, 0", BLANCO),
        _boton_momentaneo("Btn_Paro", 250, "PARO", "Cmd_Paro", "200, 0, 0", BLANCO),
        _boton_momentaneo("Btn_Reset", 363, "RESET", "Cmd_Reset", AMARILLO, GRIS_OSCURO),
    ]}

# (tag, dirección, texto, color cuando vale 1)
_FILAS_IO = [("PB_Marcha", "M10.0", "Pulsador MARCHA", VERDE), ("PB_Paro", "M10.1", "Pulsador PARO", ROJO),
             ("MOT1_Termico_Falla", "M10.2", "Térmico M1 disparado", ROJO),
             ("KM1_Motor", "M10.3", "Contactor KM1", VERDE), ("HL_Marcha", "M10.4", "Piloto marcha", VERDE),
             ("HL_Falla", "M10.5", "Piloto falla", ROJO)]

PANTALLA_DIAGNOSTICO = {
    "nombre": "Diagnostico", "numero": 2, "fondo": NEGRO, "objetos": [
        *_marco("DIAGNÓSTICO E/S"), *_navegacion("Diagnostico"),
        *[obj for i, (tag, direccion, texto, color) in enumerate(_FILAS_IO) for obj in (
            _etiqueta(f"Txt_{tag}", 137, 52 + 35 * i, 70, direccion, 14),
            _etiqueta(f"Des_{tag}", 200, 52 + 35 * i, 210, f"• {texto}", 14),
            _piloto_rect(f"Ind_{tag}", 420, 50 + 35 * i, tag, color),
        )],
    ]}

_FILAS_ESTILO = [("Banderas", "1 BANDERAS (S/R)", "Rearranca sin RESET"),
                 ("Moore", "2 MOORE (KOP)", "Falla enclavada: RESET"),
                 ("Mealy", "3 MEALY (SCL)", "Para en el mismo ciclo")]

PANTALLA_ESTILOS = {
    "nombre": "Estilos", "numero": 3, "fondo": NEGRO, "objetos": [
        *_marco("ESTILOS EN PARALELO"), *_navegacion("Estilos"),
        *[obj for i, (clave, titulo, nota) in enumerate(_FILAS_ESTILO) for obj in (
            _etiqueta(f"Tit_{clave}", 137, 50 + 55 * i, 200, titulo, 14),
            _etiqueta(f"Nota_{clave}", 137, 72 + 55 * i, 200, nota, 11, TEXTO_OSCURO, "Italic", 20),
            {"tipo": "campo_simbolico", "nombre": f"Est_{clave}", "tag": f"{clave}_Estado", "lista": "Estados",
             "modo": "salida", "x": 340, "y": 54 + 55 * i, "ancho": 90, "alto": 28,
             "fuente": {"tamano": 12, "estilo": "Bold"}},
            {"tipo": "circulo", "nombre": f"Led_{clave}", "x": 440, "y": 54 + 55 * i, "ancho": 28, "alto": 28,
             "borde": BORDE, "grosor_borde": 1,
             "apariencia": {"tag": f"{clave}_Motor", "rangos": [[0, GRIS_OSCURO], [1, VERDE]]}},
        )],
        _etiqueta("Txt_Selector", 137, 218, 120, "Manda KM1:", 14),
        {"tipo": "campo_simbolico", "nombre": "Sel_Estilo_2", "tag": "Sel_Estilo", "lista": "Estilos",
         "modo": "entrada_salida", "x": 260, "y": 214, "ancho": 150, "alto": 32,
         "fuente": {"tamano": 14, "estilo": "Bold"}},
    ]}

PANTALLAS = [PANTALLA_PRINCIPAL, PANTALLA_DIAGNOSTICO, PANTALLA_ESTILOS]
