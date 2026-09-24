from datetime import datetime

from database.db import db


class Analisis(db.Model):
    __tablename__ = "analisis"

    id = db.Column(db.Integer, primary_key=True)
    caso_estudio_id = db.Column(
        db.Integer, db.ForeignKey("casos_estudio.id"), nullable=False
    )
    problema_juridico_estudiante = db.Column(db.Text)
    normas = db.Column(db.Text)
    argumentos = db.Column(db.Text)
    decision_estudiante = db.Column(db.Text)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

    retroalimentacion = db.relationship(
        "Retroalimentacion", backref="analisis", uselist=False, lazy=True,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Analisis del caso {self.caso_estudio_id}>"
