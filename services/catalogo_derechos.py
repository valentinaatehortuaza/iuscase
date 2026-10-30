"""
Catalogo fijo de derechos fundamentales que puede invocar una sentencia de
tutela, usado para clasificar cada caso de estudio y poder agruparlos de
forma confiable en los filtros y en "Mi progreso".

La lista esta anclada en los derechos que, segun estadisticas de la Corte
Constitucional y la Defensoria del Pueblo, son los que mas se invocan en
acciones de tutela en Colombia (excluyendo "derecho de peticion", que es el
mas numeroso mas no un derecho sustantivo tipico de un caso de estudio). Se
mantiene FIJO a proposito -- un caso puede tener varios derechos (lista), pero
siempre tomados de este catalogo, nunca texto libre, para que los filtros y
las estadisticas de "Mi progreso" sigan siendo comparables entre casos.

Si se agrega o renombra un derecho aqui, hay que actualizar tambien la lista
de valores permitidos en el prompt de la Etapa 0 (servicio_ia.py).
"""

CATALOGO = {
    "salud": "Salud",
    "debido_proceso": "Debido proceso",
    "minimo_vital": "Mínimo vital",
    "vida_dignidad": "Vida y dignidad humana",
    "seguridad_social": "Seguridad social",
    "igualdad": "Igualdad y no discriminación",
    "vivienda_digna": "Vivienda digna",
    "educacion": "Educación",
    "otro": "Otro",
}


def nombre_derecho(slug):
    """Nombre legible para un slug del catalogo, o el slug tal cual si no se reconoce."""
    return CATALOGO.get(slug, slug)


def slugs_validos(lista):
    """Filtra una lista dejando solo los slugs que existen en el catalogo."""
    return [s for s in lista if s in CATALOGO]


def codificar(lista_slugs):
    """Lista de slugs -> string separado por comas, para guardar en la BD."""
    return ",".join(slugs_validos(lista_slugs or []))


def decodificar(texto):
    """String separado por comas (o None/"") -> lista de slugs."""
    if not texto:
        return []
    return [s for s in texto.split(",") if s]
