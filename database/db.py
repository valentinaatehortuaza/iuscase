from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def crear_tablas(app):
    """Crea todas las tablas en la base de datos si no existen todavia."""
    with app.app_context():
        db.create_all()
