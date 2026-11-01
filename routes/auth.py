from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import db
from models import ConsentimientoDatos, Usuario, VERSION_POLITICA_DATOS

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        nombre = request.form["nombre"].strip()
        correo = request.form["correo"].strip().lower()
        contrasena = request.form["contrasena"]

        # Autorizacion previa, expresa e informada (Ley 1581 de 2012, art. 9).
        # Se valida tambien en el servidor: el "required" del formulario se
        # puede saltar, y el silencio nunca equivale a autorizacion
        # (Decreto 1377 de 2013, art. 7).
        if request.form.get("acepta_politica") != "si":
            flash(
                "Para crear tu cuenta debes leer y aceptar la Política de "
                "tratamiento de datos personales."
            )
            return redirect(url_for("auth.registro"))

        if Usuario.query.filter_by(correo=correo).first():
            flash("Ya existe una cuenta con ese correo.")
            return redirect(url_for("auth.registro"))

        usuario = Usuario(
            nombre=nombre,
            correo=correo,
            contrasena=generate_password_hash(contrasena),
        )
        db.session.add(usuario)
        db.session.flush()  # asigna usuario.id antes de guardar el consentimiento

        # Prueba de la autorizacion (Decreto 1377 de 2013, art. 8).
        db.session.add(
            ConsentimientoDatos(
                usuario_id=usuario.id,
                version_politica=VERSION_POLITICA_DATOS,
            )
        )
        db.session.commit()

        session["usuario_id"] = usuario.id
        return redirect(url_for("dashboard.panel"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        correo = request.form["correo"].strip().lower()
        contrasena = request.form["contrasena"]

        usuario = Usuario.query.filter_by(correo=correo).first()
        if usuario is None or not check_password_hash(usuario.contrasena, contrasena):
            flash("Correo o contrasena incorrectos.")
            return redirect(url_for("auth.login"))

        session["usuario_id"] = usuario.id
        return redirect(url_for("dashboard.panel"))

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.pop("usuario_id", None)
    return redirect(url_for("inicio"))
