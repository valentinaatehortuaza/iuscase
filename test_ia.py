"""
Script rapido para verificar que la clave de Anthropic y las librerias
quedaron bien configuradas. Correlo con:  python test_ia.py
"""
from services.servicio_ia import ServicioIA

SENTENCIA_DE_PRUEBA = """
La Corte establece que el derecho a la vivienda digna debe garantizarse
de forma progresiva, y ordena al municipio reubicar a la familia
demandante en un plazo maximo de tres meses, dado el riesgo que corre
su actual lugar de residencia.
"""

if __name__ == "__main__":
    print("Probando conexion con la API de Anthropic...")
    servicio = ServicioIA()
    resultado = servicio.analizar_sentencia(SENTENCIA_DE_PRUEBA)
    print("\nConexion exitosa. La IA respondio:\n")
    print(resultado)
