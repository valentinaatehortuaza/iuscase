from datetime import datetime

from database.db import db


class CasoEstudio(db.Model):
    __tablename__ = "casos_estudio"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    sentencia_id = db.Column(db.Integer, db.ForeignKey("sentencias.id"), nullable=False)

    # ---- Etapa 0: clasificacion ----
    tipo_tutela = db.Column(db.String(30))  # particular | autoridad_publica | providencia_judicial
    fundamento_particular = db.Column(db.String(30))  # servicio_publico | interes_colectivo | subordinacion_indefension | null
    requiere_ponderacion = db.Column(db.Boolean, default=False)
    legitimacion_activa_especial = db.Column(db.String(120))

    # ---- Etapa 1: exposicion (Nivel A) ----
    nucleo_narrativo = db.Column(db.Text)
    problema_juridico = db.Column(db.Text)

    estado = db.Column(db.String(20), default="en_progreso")
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

    # ---- Etapa 4: diagnostico (agregados; el detalle vive en DiagnosticoElemento) ----
    elementos_puntuables = db.Column(db.Integer)
    puntaje_total = db.Column(db.Float)
    porcentaje_global = db.Column(db.Float)

    preguntas = db.relationship(
        "Pregunta", backref="caso_estudio", lazy=True,
        cascade="all, delete-orphan", order_by="Pregunta.orden",
    )
    diagnostico_elementos = db.relationship(
        "DiagnosticoElemento", backref="caso_estudio", lazy=True,
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<CasoEstudio {self.id}>"
