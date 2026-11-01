from datetime import datetime, timezone

from database.db import db


# Version vigente de la politica de tratamiento de datos. Si la politica cambia
# de forma sustancial, se sube este numero: asi queda registrado que version
# acepto cada usuario (Decreto 1377 de 2013, arts. 8 y 13).
VERSION_POLITICA_DATOS = "1.0"


class ConsentimientoDatos(db.Model):
    """
    Prueba de la autorizacion para el tratamiento de datos personales
    (Ley 1581 de 2012, art. 9; Decreto 1377 de 2013, art. 8: el responsable
    debe conservar prueba de la autorizacion otorgada por el titular).

    Es una tabla nueva (no una columna en "usuarios") para que db.create_all()
    la cree sola en produccion, sin necesidad de migrar la base existente.
    """

    __tablename__ = "consentimientos_datos"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    version_politica = db.Column(db.String(20), nullable=False)
    fecha_aceptacion = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self):
        return f"<ConsentimientoDatos usuario={self.usuario_id} v{self.version_politica}>"
