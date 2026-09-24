from functools import wraps

from flask import flash, redirect, session, url_for


def login_requerido(vista):
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if "usuario_id" not in session:
            flash("Debes iniciar sesion primero.")
            return redirect(url_for("auth.login"))
        return vista(*args, **kwargs)
    return envoltura
