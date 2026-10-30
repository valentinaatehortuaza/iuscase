from flask import Blueprint, render_template, session

from models import CasoEstudio
from routes.utils import login_requerido
from services.catalogo_derechos import decodificar as decodificar_derechos, nombre_derecho

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard")
@login_requerido
def panel():
    casos = (
        CasoEstudio.query
        .filter_by(usuario_id=session["usuario_id"])
        .order_by(CasoEstudio.fecha_creacion.desc())
        .all()
    )

    # etiquetas de cada tarjeta: las mas cortas primero para que alcancen a
    # compartir linea con flex-wrap en la tarjeta (ej. "Seguridad social" +
    # "Minimo vital"); la mas larga, si hay, queda al final en su propia linea
    for caso in casos:
        nombres = [nombre_derecho(slug) for slug in decodificar_derechos(caso.derechos_vulnerados)]
        caso.temas_ordenados = sorted(nombres, key=len)

    completados = [c for c in casos if c.estado == "completado"]
    puntajes = [c.porcentaje_global for c in completados if c.porcentaje_global is not None]
    promedio_puntaje = round(sum(puntajes) / len(puntajes), 1) if puntajes else None

    # ---- temas (derechos) disponibles para los chips de filtro ----
    conteo_temas = {}
    for caso in casos:
        for slug in decodificar_derechos(caso.derechos_vulnerados):
            conteo_temas[slug] = conteo_temas.get(slug, 0) + 1
    temas_disponibles = sorted(
        (
            {"slug": slug, "nombre": nombre_derecho(slug), "conteo": conteo}
            for slug, conteo in conteo_temas.items()
        ),
        key=lambda t: t["conteo"],
        reverse=True,
    )

    return render_template(
        "dashboard.html",
        casos=casos,
        total_casos=len(casos),
        casos_completados=len(completados),
        promedio_puntaje=promedio_puntaje,
        temas_disponibles=temas_disponibles,
    )
