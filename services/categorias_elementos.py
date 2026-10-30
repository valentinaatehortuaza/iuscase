"""
Traduce cada pregunta (capa + orden, segun tipo_tutela y requiere_ponderacion
del caso) a una categoria fija y legible.

Por que existe este archivo: el campo `elemento` que la IA escribe en el
diagnostico es texto libre, y puede redactarse distinto de un caso a otro
(ej. "Legitimacion activa" en un caso y "Legitimacion por activa" en otro).
Agrupar por ese texto para el panel "Mi progreso" seria poco confiable.

En cambio, la POSICION de cada pregunta (su `capa` y `orden`) esta fijada de
antemano por el prompt de servicio_ia.py segun el tipo de tutela -- eso si es
estable entre casos. Esta funcion traduce esa posicion a un nombre de
categoria consistente, sin depender de como la IA redacto el elemento ese dia.

Si cambia la estructura de preguntas en servicio_ia.py (se agrega, quita o
reordena una pregunta de alguna capa), este mapa debe actualizarse junto con
ese cambio para que seguir siendo exacto.
"""

CAPA_1 = {
    "autoridad_publica": {
        1: "Legitimación activa y pasiva",
        2: "Subsidiariedad",
        3: "Inmediatez",
    },
    "particular": {
        1: "Legitimación activa y pasiva",
        2: "Fundamento de la legitimación pasiva",
        3: "Subsidiariedad",
        4: "Inmediatez",
    },
    "providencia_judicial": {
        1: "Legitimación activa y pasiva",
        2: "Requisitos generales de procedibilidad",
        3: "Causal específica invocada",
    },
}

CAPA_2_CON_PONDERACION = {
    1: "Derechos en tensión",
    2: "Reconstrucción fáctico-normativa",
    3: "Ponderación",
    4: "Determinación motivada",
    5: "Formulación de subregla",
}

CAPA_2_SIN_PONDERACION = {
    1: "Derechos en tensión",
    2: "Reconstrucción fáctico-normativa",
    3: "Determinación motivada",
    4: "Formulación de subregla",
}


def nombre_categoria(tipo_tutela, capa, orden, requiere_ponderacion):
    """Devuelve el nombre fijo de categoria para una pregunta, o None si la
    combinacion no se reconoce (p. ej. datos antiguos de otra version del
    prompt)."""
    if capa == 1:
        return CAPA_1.get(tipo_tutela, {}).get(orden)
    if capa == 2:
        mapa = CAPA_2_CON_PONDERACION if requiere_ponderacion else CAPA_2_SIN_PONDERACION
        return mapa.get(orden)
    return None


# Explicacion en lenguaje llano de cada categoria, para mostrar junto al
# nombre tecnico en "Mi progreso" (el estudiante ve el termino juridico,
# pero no siempre recuerda a que habilidad puntual corresponde).
DESCRIPCIONES = {
    "Legitimación activa y pasiva": "Identificar quién puede presentar la tutela y contra quién se dirige",
    "Fundamento de la legitimación pasiva": "Justificar por qué esa entidad o persona puede ser demandada en tutela",
    "Subsidiariedad": "Explicar por qué la tutela procede aunque existan otros mecanismos de defensa",
    "Inmediatez": "Justificar que la tutela se presentó en un tiempo razonable desde los hechos",
    "Requisitos generales de procedibilidad": "Verificar que se cumplan los requisitos para que la tutela proceda contra una providencia judicial",
    "Causal específica invocada": "Sustentar la causal específica por la que procede la tutela contra esa providencia",
    "Derechos en tensión": "Identificar los derechos fundamentales que están en conflicto en el caso",
    "Reconstrucción fáctico-normativa": "Conectar los hechos del caso con las normas y precedentes aplicables",
    "Ponderación": "Sopesar los derechos en conflicto para definir cuál debe prevalecer",
    "Determinación motivada": "Justificar con argumentos la decisión que se toma sobre el caso",
    "Formulación de subregla": "Redactar la regla jurídica concreta que resuelve el caso",
}


def descripcion_categoria(nombre_categoria_fija):
    """Explicacion en lenguaje llano de una categoria ya resuelta por
    nombre_categoria(), o cadena vacia si no hay una registrada."""
    return DESCRIPCIONES.get(nombre_categoria_fija, "")
