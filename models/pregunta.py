from database.db import db


class Pregunta(db.Model):
    __tablename__ = "preguntas"

    id = db.Column(db.Integer, primary_key=True)
    caso_estudio_id = db.Column(
        db.Integer, db.ForeignKey("casos_estudio.id"), nullable=False
    )
    capa = db.Column(db.Integer, nullable=False)  # 1 = filtro procesal, 2 = analisis sustantivo
    hechos_relevantes = db.Column(db.Text)  # "Hechos relevantes para esta pregunta" (Nivel B)
    enunciado = db.Column(db.Text, nullable=False)
    orden = db.Column(db.Integer)

    respuesta = db.relationship(
        "Respuesta", backref="pregunta", uselist=False, lazy=True,
        cascade="all, delete-orphan"
    )
    diagnostico = db.relationship(
        "DiagnosticoElemento", backref="pregunta", uselist=False, lazy=True,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Pregunta {self.orden} (capa {self.capa})>"
