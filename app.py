import truststore
truststore.inject_into_ssl()  # usa la verificacion de certificados del sistema (como el navegador)

import os

from flask import Flask, flash, redirect, render_template, url_for

from database.db import db, crear_tablas
from models import (
    Usuario,
    Sentencia,
    CasoEstudio,
    Pregunta,
    Respuesta,
    DiagnosticoElemento,
)
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.casos import casos_bp

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///iuscase.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "cambia-esto-antes-de-publicar")
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB por archivo subido

db.init_app(app)

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(casos_bp)

# Se ejecuta siempre al cargar el modulo (tanto con "python app.py" como con
# gunicorn en produccion, que importa "app" sin pasar por el bloque de abajo).
crear_tablas(app)


@app.route("/")
def inicio():
    return render_template("index.html")


@app.errorhandler(413)
def archivo_muy_grande(e):
    flash("El archivo es demasiado grande (máximo 20 MB).")
    return redirect(url_for("casos.subir_sentencia"))


if __name__ == "__main__":
    app.run(debug=True, port=5001)
