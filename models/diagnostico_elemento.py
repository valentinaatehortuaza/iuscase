from database.db import db


class DiagnosticoElemento(db.Model):
    """Resultado de la Etapa 4 (contraste y diagnostico) para UNA pregunta/elemento."""

    __tablename__ = "diagnostico_elementos"

    id = db.Column(db.Integer, primary_key=True)
    caso_estudio_id = db.Column(
        db.Integer, db.ForeignKey("casos_estudio.id"), nullable=False
    )
    pregunta_id = db.Column(db.Integer, db.ForeignKey("preguntas.id"), nullable=False)

    elemento = db.Column(db.String(255))  # nombre corto del elemento evaluado
    respuesta_estudiante = db.Column(db.Text)
    veredicto = db.Column(db.String(20))  # acertado | incompleto | incorrecto | no_aplicable
    explicacion = db.Column(db.Text)
    fragmento_sentencia = db.Column(db.Text)
    puntos = db.Column(db.Float)

    def __repr__(self):
        return f"<DiagnosticoElemento {self.elemento} ({self.veredicto})>"
