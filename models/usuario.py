from database.db import db


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    correo = db.Column(db.String(120), unique=True, nullable=False)
    contrasena = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(20), default="estudiante")

    sentencias = db.relationship("Sentencia", backref="usuario", lazy=True)
    casos = db.relationship("CasoEstudio", backref="usuario", lazy=True)

    def __repr__(self):
        return f"<Usuario {self.correo}>"
