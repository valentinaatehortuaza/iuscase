from database.db import db


class Sentencia(db.Model):
    __tablename__ = "sentencias"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    titulo = db.Column(db.String(255), nullable=False)
    tribunal = db.Column(db.String(255))
    fecha = db.Column(db.Date)
    texto = db.Column(db.Text)
    archivo = db.Column(db.String(255))

    caso_estudio = db.relationship(
        "CasoEstudio", backref="sentencia", uselist=False, lazy=True
    )

    def __repr__(self):
        return f"<Sentencia {self.titulo}>"
