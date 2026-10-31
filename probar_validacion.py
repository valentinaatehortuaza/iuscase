"""Prueba rapida y barata de validar_es_sentencia_tutela (no modifica la BD)."""
import sqlite3
from services.servicio_ia import ServicioIA

sv = ServicioIA()

# Caso 1: texto que SI es una sentencia de tutela real (la mas corta que tiene cargada).
con = sqlite3.connect("instance/iuscase.db")
cur = con.cursor()
cur.execute("SELECT titulo, texto FROM sentencias WHERE id = 1")
titulo, texto_real = cur.fetchone()
con.close()

print(f"Caso 1: sentencia real ({titulo}, {len(texto_real):,} caracteres)")
r1 = sv.validar_es_sentencia_tutela(texto_real)
print(f"  -> {r1}\n")

# Caso 2: texto que NO es una sentencia de tutela (un contrato de arrendamiento inventado).
texto_falso = """
CONTRATO DE ARRENDAMIENTO DE VIVIENDA URBANA

Entre los suscritos, JUAN PEREZ GOMEZ, mayor de edad, identificado con cedula
de ciudadania No. 12.345.678, quien en adelante se denominara EL ARRENDADOR,
y MARIA LOPEZ RUIZ, identificada con cedula de ciudadania No. 98.765.432,
quien en adelante se denominara LA ARRENDATARIA, se ha celebrado el presente
contrato de arrendamiento, el cual se regira por las siguientes clausulas:

PRIMERA. OBJETO: El arrendador entrega a titulo de arrendamiento al
arrendatario el inmueble ubicado en la Calle 45 No. 23-10, Apartamento 301,
de la ciudad de Bogota D.C.

SEGUNDA. CANON DE ARRENDAMIENTO: El canon mensual de arrendamiento sera la
suma de UN MILLON DOSCIENTOS MIL PESOS ($1.200.000) moneda corriente,
pagaderos dentro de los primeros cinco (5) dias de cada mes.

TERCERA. DURACION: El presente contrato tendra una duracion de doce (12)
meses contados a partir de la fecha de suscripcion, prorrogables
automaticamente por periodos iguales salvo aviso en contrario de cualquiera
de las partes con una antelacion no inferior a treinta (30) dias.

CUARTA. DEPOSITO: La arrendataria entrega en este acto, a titulo de
deposito, la suma de UN MILLON DOSCIENTOS MIL PESOS ($1.200.000), que sera
devuelta al finalizar el contrato previa verificacion del estado del
inmueble.

En constancia se firma en dos ejemplares del mismo tenor, en Bogota D.C.,
a los quince (15) dias del mes de marzo de 2026.
"""
print(f"Caso 2: contrato (no sentencia), {len(texto_falso):,} caracteres")
r2 = sv.validar_es_sentencia_tutela(texto_falso)
print(f"  -> {r2}")

tokens_entrada, tokens_salida = sv.obtener_y_reiniciar_uso()
print(f"\nTokens usados en esta prueba: entrada={tokens_entrada:,}  salida={tokens_salida:,}")
