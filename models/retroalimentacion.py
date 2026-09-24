from datetime import datetime

from database.db import db


class Retroalimentacion(db.Model):
    __tablename__ = "retroalimentaciones"

    id = db.Column(db.Integer, primary_key=True)
    analisis_id = db.Column(db.Integer, db.ForeignKey("analisis.id"), nullable=False)
    coherencia = db.Column(db.String(50))
    fortalezas = db.Column(db.Text)
    debilidades = db.Column(db.Text)
    sugerencias = db.Column(db.Text)
    resultado = db.Column(db.String(50))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Retroalimentacion del analisis {self.analisis_id}>"
