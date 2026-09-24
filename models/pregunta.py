from database.db import db


class Pregunta(db.Model):
    __tablename__ = "preguntas"

    id = db.Column(db.Integer, primary_key=True)
    caso_estudio_id = db.Column(
        db.Integer, db.ForeignKey("casos_estudio.id"), nullable=False
    )
    enunciado = db.Column(db.Text, nullable=False)
    tipo = db.Column(db.String(50))
    orden = db.Column(db.Integer)

    respuesta = db.relationship(
        "Respuesta", backref="pregunta", uselist=False, lazy=True,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Pregunta {self.orden}>"
