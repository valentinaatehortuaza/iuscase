import os
import traceback
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from database.db import db
from models import (
    CasoEstudio,
    DiagnosticoElemento,
    Pregunta,
    Respuesta,
    Sentencia,
)
from routes.utils import login_requerido
from services.servicio_ia import ServicioIA

casos_bp = Blueprint("casos", __name__)
servicio_ia = ServicioIA()

CARPETA_UPLOADS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
EXTENSIONES_PERMITIDAS = {"pdf"}
LIMITE_DESCARGA_BYTES = 20 * 1024 * 1024  # 20 MB, igual que el limite de subida de archivos


def _extension_permitida(nombre_archivo):
    return "." in nombre_archivo and nombre_archivo.rsplit(".", 1)[1].lower() in EXTENSIONES_PERMITIDAS


def _extraer_texto_pdf(ruta_pdf):
    from pypdf import PdfReader

    lector = PdfReader(ruta_pdf)
    paginas = [pagina.extract_text() or "" for pagina in lector.pages]
    return "\n".join(paginas).strip()


def _extraer_texto_html(html):
    sopa = BeautifulSoup(html, "html.parser")
    for etiqueta in sopa(["script", "style"]):
        etiqueta.decompose()
    texto = sopa.get_text(separator="\n")
    lineas = [linea.strip() for linea in texto.splitlines()]
    return "\n".join(linea for linea in lineas if linea)


def _descargar_desde_url(url):
    """Descarga el contenido de un link a una sentencia (PDF o pagina HTML)."""
    encabezados = {"User-Agent": "Mozilla/5.0 (IUSCase, prototipo educativo)"}
    respuesta = requests.get(url, timeout=15, headers=encabezados, stream=True)
    respuesta.raise_for_status()

    contenido = respuesta.raw.read(LIMITE_DESCARGA_BYTES + 1, decode_content=True)
    if len(contenido) > LIMITE_DESCARGA_BYTES:
        raise ValueError("El archivo del link supera el limite de 20 MB.")

    tipo_contenido = respuesta.headers.get("Content-Type", "").lower()

    if "pdf" in tipo_contenido or url.lower().split("?")[0].endswith(".pdf"):
        os.makedirs(CARPETA_UPLOADS, exist_ok=True)
        nombre_archivo_guardado = f"url_{int(datetime.utcnow().timestamp())}.pdf"
        ruta_guardada = os.path.join(CARPETA_UPLOADS, nombre_archivo_guardado)
        with open(ruta_guardada, "wb") as f:
            f.write(contenido)
        return _extraer_texto_pdf(ruta_guardada), nombre_archivo_guardado

    codificacion = respuesta.encoding or "utf-8"
    html = contenido.decode(codificacion, errors="ignore")
    return _extraer_texto_html(html), None


@casos_bp.route("/subir-sentencia", methods=["GET", "POST"])
@login_requerido
def subir_sentencia():
    if request.method == "POST":
        titulo = request.form["titulo"].strip()
        texto = request.form.get("texto", "").strip()
        url_sentencia = request.form.get("url_sentencia", "").strip()
        archivo = request.files.get("archivo_pdf")
        nombre_archivo_guardado = None

        if archivo and archivo.filename:
            if not _extension_permitida(archivo.filename):
                flash("Solo se aceptan archivos PDF.")
                return redirect(url_for("casos.subir_sentencia"))

            nombre_seguro = secure_filename(archivo.filename)
            marca_tiempo = int(datetime.utcnow().timestamp())
            nombre_archivo_guardado = f"{session['usuario_id']}_{marca_tiempo}_{nombre_seguro}"

            os.makedirs(CARPETA_UPLOADS, exist_ok=True)
            ruta_guardada = os.path.join(CARPETA_UPLOADS, nombre_archivo_guardado)
            archivo.save(ruta_guardada)

            texto_extraido = _extraer_texto_pdf(ruta_guardada)
            if len(texto_extraido) < 200:
                flash(
                    "No se pudo extraer texto legible de ese PDF (puede ser un "
                    "escaneo sin texto seleccionable). Intenta pegar el texto "
                    "directamente en el campo de abajo."
                )
                return redirect(url_for("casos.subir_sentencia"))
            texto = texto_extraido

        elif url_sentencia:
            if not url_sentencia.startswith(("http://", "https://")):
                flash("El link debe empezar con http:// o https://")
                return redirect(url_for("casos.subir_sentencia"))

            try:
                texto_extraido, nombre_archivo_guardado = _descargar_desde_url(url_sentencia)
            except (requests.RequestException, ValueError) as error:
                print("ERROR al descargar el link de la sentencia:")
                traceback.print_exc()
                flash(
                    f"No se pudo descargar el contenido de ese link ({error}). "
                    "Verifica que sea correcto y publico, o intenta pegar el "
                    "texto directamente."
                )
                return redirect(url_for("casos.subir_sentencia"))

            if len(texto_extraido) < 200:
                flash(
                    "No se pudo extraer texto legible de ese link. Intenta pegar "
                    "el texto directamente en el campo de abajo."
                )
                return redirect(url_for("casos.subir_sentencia"))
            texto = texto_extraido

        if not texto:
            flash("Debes subir un PDF, pegar un link o pegar el texto de la sentencia.")
            return redirect(url_for("casos.subir_sentencia"))

        sentencia = Sentencia(
            usuario_id=session["usuario_id"],
            titulo=titulo,
            tribunal="Corte Constitucional",
            texto=texto,
            archivo=nombre_archivo_guardado,
        )
        db.session.add(sentencia)
        db.session.commit()

        # Etapa 0: clasificacion
        clasificacion = servicio_ia.clasificar_sentencia(texto)

        # Etapa 1 (Nivel A): nucleo narrativo + problema juridico
        exposicion = servicio_ia.generar_nucleo_narrativo(texto, clasificacion)

        # Etapa 2: preguntas guia, en llamadas separadas por capa (cada una
        # con su propio bloque de "hechos relevantes" - Nivel B) para que
        # ninguna llamada individual a la IA tenga que generar demasiado
        # contenido de una sola vez.
        preguntas_capa1 = servicio_ia.generar_preguntas_capa1(
            texto, clasificacion, exposicion.get("nucleo_narrativo")
        )
        preguntas_capa2 = servicio_ia.generar_preguntas_capa2(
            texto, clasificacion, exposicion.get("nucleo_narrativo")
        )

        caso = CasoEstudio(
            usuario_id=session["usuario_id"],
            sentencia_id=sentencia.id,
            tipo_tutela=clasificacion.get("tipo_tutela"),
            fundamento_particular=clasificacion.get("fundamento_particular"),
            requiere_ponderacion=bool(clasificacion.get("requiere_ponderacion")),
            legitimacion_activa_especial=clasificacion.get("legitimacion_activa_especial"),
            nucleo_narrativo=exposicion.get("nucleo_narrativo"),
            problema_juridico=exposicion.get("problema_juridico"),
        )
        db.session.add(caso)
        db.session.commit()

        orden = 1
        for capa, preguntas in ((1, preguntas_capa1), (2, preguntas_capa2)):
            for p in preguntas:
                db.session.add(Pregunta(
                    caso_estudio_id=caso.id,
                    capa=capa,
                    hechos_relevantes=p.get("hechos_relevantes"),
                    enunciado=p["texto"],
                    orden=orden,
                ))
                orden += 1

        db.session.commit()

        return redirect(url_for("casos.resolver_caso", caso_id=caso.id))

    return render_template("subir_sentencia.html")


@casos_bp.route("/caso/<int:caso_id>/resolver", methods=["GET", "POST"])
@login_requerido
def resolver_caso(caso_id):
    caso = CasoEstudio.query.filter_by(
        id=caso_id, usuario_id=session["usuario_id"]
    ).first_or_404()

    if caso.estado == "completado":
        return redirect(url_for("casos.ver_retroalimentacion", caso_id=caso.id))

    preguntas_ordenadas = sorted(caso.preguntas, key=lambda p: p.orden or 0)

    if request.method == "POST":
        # Etapa 3: se guardan las respuestas del estudiante (no se genera nada aqui)
        paquete_para_ia = []
        for pregunta in preguntas_ordenadas:
            texto_respuesta = request.form.get(f"respuesta_{pregunta.id}", "").strip()
            db.session.add(Respuesta(pregunta_id=pregunta.id, texto=texto_respuesta))
            paquete_para_ia.append({
                "pregunta": pregunta.enunciado,
                "hechos_relevantes": pregunta.hechos_relevantes,
                "respuesta_estudiante": texto_respuesta,
            })
        db.session.commit()

        # Etapa 4: contraste y diagnostico, elemento por elemento
        diagnostico = servicio_ia.generar_diagnostico(caso.sentencia.texto, paquete_para_ia)
        elementos = diagnostico.get("elementos", [])

        puntaje_total = 0.0
        elementos_puntuables = 0

        for pregunta, elem in zip(preguntas_ordenadas, elementos):
            puntos = elem.get("puntos")
            veredicto = elem.get("veredicto")
            if veredicto != "no_aplicable" and puntos is not None:
                puntaje_total += puntos
                elementos_puntuables += 1

            db.session.add(DiagnosticoElemento(
                caso_estudio_id=caso.id,
                pregunta_id=pregunta.id,
                elemento=elem.get("elemento"),
                respuesta_estudiante=elem.get("respuesta_estudiante"),
                veredicto=veredicto,
                explicacion=elem.get("explicacion"),
                fragmento_sentencia=elem.get("fragmento_sentencia"),
                puntos=puntos,
            ))

        caso.elementos_puntuables = elementos_puntuables
        caso.puntaje_total = puntaje_total
        caso.porcentaje_global = (
            round(puntaje_total / elementos_puntuables * 100, 1)
            if elementos_puntuables else None
        )
        caso.estado = "completado"
        db.session.commit()

        return redirect(url_for("casos.ver_retroalimentacion", caso_id=caso.id))

    return render_template("resolver_caso.html", caso=caso, preguntas=preguntas_ordenadas)


@casos_bp.route("/caso/<int:caso_id>/retroalimentacion")
@login_requerido
def ver_retroalimentacion(caso_id):
    caso = CasoEstudio.query.filter_by(
        id=caso_id, usuario_id=session["usuario_id"]
    ).first_or_404()

    if caso.estado != "completado":
        flash("Todavia no has completado este caso.")
        return redirect(url_for("casos.resolver_caso", caso_id=caso.id))

    diagnostico_ordenado = sorted(
        caso.diagnostico_elementos, key=lambda d: (d.pregunta.orden or 0)
    )

    return render_template(
        "retroalimentacion.html",
        caso=caso,
        diagnostico=diagnostico_ordenado,
    )
