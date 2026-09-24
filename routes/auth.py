from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import db
from models import Usuario

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        nombre = request.form["nombre"].strip()
        correo = request.form["correo"].strip().lower()
        contrasena = request.form["contrasena"]

        if Usuario.query.filter_by(correo=correo).first():
            flash("Ya existe una cuenta con ese correo.")
            return redirect(url_for("auth.registro"))

        usuario = Usuario(
            nombre=nombre,
            correo=correo,
            contrasena=generate_password_hash(contrasena),
        )
        db.session.add(usuario)
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
