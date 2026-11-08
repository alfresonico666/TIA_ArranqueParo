# Perfil de estilo: ArranqueParo_v2

Generado automáticamente por TIA_MCP_V17. Úsalo como guía para programar igual que este proyecto.

## Estructura
- Bloques: 10 → InstanceDB/DB: 4, FB/LAD: 3, OB/LAD: 1, GlobalDB/DB: 1, FB/SCL: 1
- Redes: 37 | con título: 97 % | con comentario: 59 %
- Instancias: 1 multiinstancia (#) / 4 DB individual

## Convenciones de nombres
- Estilo predominante: Snake_Case (15), PascalCase (1)
- OB: prefijos sin prefijo fijo; ej.: Main
- FB: prefijos FB_ (100 %); ej.: FB_Mando_Motor, FB_Motor_Banderas, FB_Motor_Moore, FB_Motor_Mealy
- GlobalDB: prefijos sin prefijo fijo; ej.: DB_HMI
- InstanceDB: prefijos DB_ (100 %); ej.: DB_Mando, DB_Motor_Banderas, DB_Motor_Moore, DB_Motor_Mealy
- Interfaz Input: prefijos HMI_ (16 %), PB_ (11 %); ej.: PB_Marcha, PB_Paro_NC, Termico_NC, HMI_Marcha, HMI_Paro, HMI_Reset
- Interfaz Output: prefijos sin prefijo fijo; ej.: Marcha, Paro, Termico_OK, Reset, Motor, Piloto_Marcha
- Interfaz Static: prefijos Cmd_ (21 %), B_ (14 %); ej.: Cmd_Marcha, Cmd_Paro, Cmd_Reset, Sel_Estilo, Estado, Motor_En_Marcha
- Interfaz Temp: prefijos sin prefijo fijo; ej.: Estado_Previo, Estado_Previo
- Tags: 6, con comentario 100 %; prefijos PB_ (33 %), HL_ (33 %)
  ej.: PB_Marcha %M10.0, PB_Paro_NC %M10.1, MOT1_Termico_NC %M10.2, KM1_Motor %M10.3, HL_Marcha %M10.4, HL_Falla %M10.5

## Instrucciones más usadas
- Contact (40), Eq (20), Move (18), Coil (17), Call FB_Mando_Motor (6), Call FB_Motor_Banderas (4), Call FB_Motor_Moore (4), Call FB_Motor_Mealy (4), SCoil (1), RCoil (1)

## Árbol de llamadas
```
Main
  FB_Mando_Motor  ("DB_Mando")
  FB_Motor_Banderas  ("DB_Motor_Banderas")
  FB_Motor_Moore  ("DB_Motor_Moore")
  FB_Motor_Mealy  ("DB_Motor_Mealy")
```

## Redes de ejemplo
### FB_Mando_Motor › Red 4: MARCHA mantenida 3 s
> Patrón de reset probado: mantener el pulsador 3 s.
```
#T_Reset TON(IN:=#PB_Marcha, PT:=T#3s)
#Reset_Mantenido := #T_Reset.Q
```
### Main › Red 1: MANDO: pulsadores + HMI
> Une entradas físicas y botones de la HMI.
```
CALL "FB_Mando_Motor" ("DB_Mando")(en:=1, PB_Marcha:="PB_Marcha", PB_Paro_NC:="PB_Paro_NC", Termico_NC:="MOT1_Termico_NC", HMI_Marcha:="DB_HMI".Cmd_Marcha, HMI_Paro:="DB_HMI".Cmd_Paro, HMI_Reset:="DB_HMI".Cmd_Reset)
```
### Main › Red 2: ESTILO 1: BANDERAS (S/R)
```
CALL "FB_Motor_Banderas" ("DB_Motor_Banderas")(en:=1, Marcha:="DB_Mando".Marcha, Paro:="DB_Mando".Paro, Termico_OK:="DB_Mando".Termico_OK, Reset:="DB_Mando".Reset)
```
