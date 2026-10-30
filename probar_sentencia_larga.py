"""
Script de prueba manual (no es parte de la app) para medir cuanto tarda el
flujo completo de "subir sentencia" con una sentencia LARGA real, y para ver
en vivo el efecto del prompt caching (cuantos tokens se leen del cache vs se
cobran completos) en cada una de las 4 llamadas que se disparan juntas al
subir una sentencia.

Usa la sentencia T-014/26 (id=13 en tu base de datos), que con 211,756
caracteres es la mas larga que tienes cargada -- el peor caso real para
medir el riesgo de que Render corte la peticion por timeout.

Como correrlo:
    cd ~/Desktop/IUSCase          (o la carpeta de tu proyecto)
    source .venv/bin/activate     (o como actives tu entorno)
    python3 probar_sentencia_larga.py

No modifica la base de datos ni crea un caso nuevo -- solo llama a la IA y
mide tiempos/tokens.
"""

import sqlite3
import time

from services import servicio_ia

ID_SENTENCIA = 13


def obtener_texto_sentencia(id_sentencia):
    con = sqlite3.connect("instance/iuscase.db")
    cur = con.cursor()
    cur.execute("SELECT titulo, texto FROM sentencias WHERE id = ?", (id_sentencia,))
    fila = cur.fetchone()
    con.close()
    if not fila:
        raise SystemExit(f"No existe la sentencia id={id_sentencia} en instance/iuscase.db")
    return fila[0], fila[1]


def main():
    titulo, texto = obtener_texto_sentencia(ID_SENTENCIA)
    print(f"Sentencia: {titulo}  |  {len(texto):,} caracteres\n")

    sv = servicio_ia.ServicioIA()

    # Envolvemos el cliente de Anthropic para imprimir, llamada por llamada,
    # cuanto tardo y como vino desglosado el uso de tokens (cuantos se
    # cobraron completos, cuantos fueron escritura de cache y cuantos fueron
    # lectura de cache a ~10% del precio). Esto es solo para esta prueba --
    # no toca el codigo real de la app.
    llamada_create_original = sv._cliente.messages.create

    def create_con_log(*args, **kwargs):
        t0 = time.time()
        respuesta = llamada_create_original(*args, **kwargs)
        duracion = time.time() - t0
        u = respuesta.usage
        creacion = getattr(u, "cache_creation_input_tokens", 0) or 0
        lectura = getattr(u, "cache_read_input_tokens", 0) or 0
        print(
            f"    {duracion:5.1f}s  |  input normal: {u.input_tokens:>6}  "
            f"|  escritura a cache: {creacion:>6}  |  lectura de cache: {lectura:>6}  "
            f"|  salida: {u.output_tokens:>5}"
        )
        return respuesta

    sv._cliente.messages.create = create_con_log

    t_inicio = time.time()

    print("1) clasificar_sentencia (primera llamada: aqui se ESCRIBE el cache, no hay ahorro todavia)")
    clasificacion = sv.clasificar_sentencia(texto)

    print("2) generar_nucleo_narrativo (deberia LEER del cache -> mucho mas barata)")
    exposicion = sv.generar_nucleo_narrativo(texto, clasificacion)

    print("3) generar_preguntas_capa1 (deberia LEER del cache)")
    sv.generar_preguntas_capa1(texto, clasificacion, exposicion.get("nucleo_narrativo"))

    print("4) generar_preguntas_capa2 (deberia LEER del cache)")
    sv.generar_preguntas_capa2(texto, clasificacion, exposicion.get("nucleo_narrativo"))

    total = time.time() - t_inicio
    tokens_entrada, tokens_salida = sv.obtener_y_reiniciar_uso()

    print(f"\nTiempo total de las 4 llamadas (lo que tarda subir esta sentencia): {total:.1f}s")
    print(f"Tokens de entrada acumulados: {tokens_entrada:,}  |  tokens de salida: {tokens_salida:,}")
    print(
        "\nSi el numero de arriba se acerca o supera el timeout de tu hosting "
        "(revisa el limite de Render para peticiones HTTP), esa es la senal de "
        "que este flujo sincrono de 4 llamadas es un riesgo real para "
        "sentencias largas y conviene mover la subida a un proceso en "
        "segundo plano antes de la entrega."
    )


if __name__ == "__main__":
    main()
