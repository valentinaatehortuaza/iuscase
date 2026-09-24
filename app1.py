from models.usuario import Usuario
from models.sentencia import Sentencia
from models.caso_estudio import CasoEstudio
from models.pregunta import Pregunta
from models.respuesta import Respuesta
from models.analisis import Analisis
from models.decision_judicial import DecisionJudicial
from models.retroalimentacion import Retroalimentacion

# ==========================
# CREAR USUARIO
# ==========================
usuario1 = Usuario(
    1,
    "Valentina",
    "valentina@gmail.com"
)

# ==========================
# CREAR SENTENCIA
# ==========================
sentencia1 = Sentencia(
    1,
    "Caso sobre libertad de expresión",
    "Corte Constitucional",
    "2025-03-10",
    "Contenido de la sentencia...",
    "sentencia.pdf"
)

# ==========================
# CREAR CASO DE ESTUDIO
# ==========================
caso1 = CasoEstudio(
    1,
    "Una persona publicó información sobre otra.",
    "El conflicto gira alrededor del derecho al buen nombre.",
    "¿Se vulneró el derecho al buen nombre?",
    sentencia1
)

# ==========================
# CREAR PREGUNTA
# ==========================
pregunta1 = Pregunta(
    1,
    "¿Cuál considera que es el problema jurídico principal del caso?",
    "Problema Jurídico",
    1
)

# ==========================
# CREAR RESPUESTA
# ==========================
respuesta1 = Respuesta(
    1,
    "Considero que la publicación vulneró el derecho al buen nombre.",
    "2026-09-06"
)

# ==========================
# CREAR ANÁLISIS
# ==========================
analisis1 = Analisis(
    "¿Se vulneró el derecho al buen nombre?",
    "Artículo 15 de la Constitución Política",
    "La publicación afecta la reputación de la persona.",
    "Sí existe vulneración."
)

# ==========================
# CREAR DECISIÓN JUDICIAL
# ==========================
decision1 = DecisionJudicial(
    1,
    "Se concede la protección del derecho al buen nombre.",
    "La Corte encontró una afectación injustificada.",
    "Se concede el amparo."
)

# ==========================
# MOSTRAR INFORMACIÓN
# ==========================
print("===== USUARIO =====")
print(usuario1.nombre)
print(usuario1.correo)

print("\n===== SENTENCIA =====")
print(sentencia1.titulo)
print(sentencia1.tribunal)

print("\n===== CASO DE ESTUDIO =====")
print(caso1.hechos)
print(caso1.contexto)
print(caso1.problema_juridico)
print("Sentencia asociada:", caso1.sentencia.titulo)

print("\n===== PREGUNTA =====")
print(pregunta1.enunciado)

print("\n===== RESPUESTA =====")
print(respuesta1.texto)

print("\n===== ANÁLISIS =====")
print(analisis1.problema_juridico)
print(analisis1.normas)
print(analisis1.argumentos)
print(analisis1.decision_estudiante)

print("\n===== DECISIÓN JUDICIAL =====")
print(decision1.decision)
print(decision1.fundamentos)
print(decision1.resultado)

print("\n===== RETROALIMENTACIÓN =====")
print(retro1.coherencia)
print(retro1.fortalezas)
print(retro1.aspectos_mejorar)
print(retro1.sugerencias)
print(retro1.calificacion)