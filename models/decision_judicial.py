from database.db import db


class DecisionJudicial(db.Model):
    __tablename__ = "decisiones_judiciales"

    id = db.Column(db.Integer, primary_key=True)
    caso_estudio_id = db.Column(
        db.Integer, db.ForeignKey("casos_estudio.id"), nullable=False
    )
    decision = db.Column(db.Text)
    fundamentos = db.Column(db.Text)
    resultado = db.Column(db.Text)

    def __repr__(self):
        return f"<DecisionJudicial del caso {self.caso_estudio_id}>"
