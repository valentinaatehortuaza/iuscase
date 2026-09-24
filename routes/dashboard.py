from flask import Blueprint, render_template, session

from models import CasoEstudio
from routes.utils import login_requerido

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
    return render_template("dashboard.html", casos=casos)
