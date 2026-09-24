from datetime import datetime

from database.db import db


class CasoEstudio(db.Model):
    __tablename__ = "casos_estudio"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    sentencia_id = db.Column(db.Integer, db.ForeignKey("sentencias.id"), nullable=False)
    hechos = db.Column(db.Text)
    contexto = db.Column(db.Text)
    problema_juridico = db.Column(db.Text)
    actores = db.Column(db.Text)
    elementos_clave = db.Column(db.Text)
    estado = db.Column(db.String(20), default="en_progreso")
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

    preguntas = db.relationship(
        "Pregunta", backref="caso_estudio", lazy=True, cascade="all, delete-orphan"
    )
    analisis = db.relationship(
        "Analisis", backref="caso_estudio", uselist=False, lazy=True,
        cascade="all, delete-orphan"
    )
    decision_judicial = db.relationship(
        "DecisionJudicial", backref="caso_estudio", uselist=False, lazy=True,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<CasoEstudio {self.id}>"
