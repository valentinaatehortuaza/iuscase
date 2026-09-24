import os
import traceback
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from database.db import db
from models import (
    Analisis,
    CasoEstudio,
    DecisionJudicial,
    Pregunta,
    Respuesta,
    Retroalimentacion,
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
        tribunal = request.form.get("tribunal", "").strip()
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
            tribunal=tribunal or None,
            texto=texto,
            archivo=nombre_archivo_guardado,
        )
        db.session.add(sentencia)
        db.session.commit()

        # Paso 2: comprimir el problema juridico central
        resumen = servicio_ia.analizar_sentencia(texto)

        # Paso 3: construir el caso de estudio (sin revelar el fallo)
        caso_generado = servicio_ia.generar_caso(texto, resumen["problema_juridico"])

        caso = CasoEstudio(
            usuario_id=session["usuario_id"],
            sentencia_id=sentencia.id,
            hechos=caso_generado["hechos"],
            contexto=caso_generado["contexto"],
            problema_juridico=resumen["problema_juridico"],
            actores="\n".join(caso_generado.get("actores", [])),
            elementos_clave="\n".join(caso_generado.get("elementos_clave", [])),
        )
        db.session.add(caso)
        db.session.commit()

        # La decision real se guarda ya, pero no se muestra hasta el final
        decision_extraida = servicio_ia.extraer_decision_judicial(texto)
        db.session.add(DecisionJudicial(
            caso_estudio_id=caso.id,
            decision=decision_extraida["decision"],
            fundamentos=decision_extraida["fundamentos"],
            resultado=decision_extraida["resultado"],
        ))

        # Paso 4: preguntas guia
        for p in servicio_ia.generar_preguntas(caso):
            db.session.add(Pregunta(
                caso_estudio_id=caso.id,
                enunciado=p["enunciado"],
                tipo=p["tipo"],
                orden=p["orden"],
            ))

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

    if request.method == "POST":
        # Paso 5: guardar las respuestas del estudiante, agrupadas por tipo
        respuestas_por_tipo = {}
        for pregunta in caso.preguntas:
            texto_respuesta = request.form.get(f"respuesta_{pregunta.id}", "").strip()
            db.session.add(Respuesta(pregunta_id=pregunta.id, texto=texto_respuesta))
            respuestas_por_tipo.setdefault(pregunta.tipo, []).append(texto_respuesta)
        db.session.commit()

        analisis = Analisis(
            caso_estudio_id=caso.id,
            problema_juridico_estudiante=caso.problema_juridico,
            normas="\n".join(respuestas_por_tipo.get("normas", [])),
            argumentos="\n".join(
                respuestas_por_tipo.get("argumentos", [])
                + respuestas_por_tipo.get("otro", [])
            ),
            decision_estudiante="\n".join(respuestas_por_tipo.get("decision", [])),
        )
        db.session.add(analisis)
        db.session.commit()

        # Paso 6: comparar con la decision real y generar retroalimentacion
        comparacion = servicio_ia.comparar_decision(analisis, caso.decision_judicial)
        retro_generada = servicio_ia.generar_retroalimentacion(comparacion)

        db.session.add(Retroalimentacion(
            analisis_id=analisis.id,
            coherencia=retro_generada["coherencia"],
            fortalezas=retro_generada["fortalezas"],
            debilidades=retro_generada["debilidades"],
            sugerencias=retro_generada["sugerencias"],
            resultado=retro_generada["resultado"],
        ))

        caso.estado = "completado"
        db.session.commit()

        return redirect(url_for("casos.ver_retroalimentacion", caso_id=caso.id))

    return render_template("resolver_caso.html", caso=caso)


@casos_bp.route("/caso/<int:caso_id>/retroalimentacion")
@login_requerido
def ver_retroalimentacion(caso_id):
    caso = CasoEstudio.query.filter_by(
        id=caso_id, usuario_id=session["usuario_id"]
    ).first_or_404()

    if caso.estado != "completado" or caso.analisis is None:
        flash("Todavia no has completado este caso.")
        return redirect(url_for("casos.resolver_caso", caso_id=caso.id))

    return render_template(
        "retroalimentacion.html",
        caso=caso,
        analisis=caso.analisis,
        decision=caso.decision_judicial,
        retro=caso.analisis.retroalimentacion,
    )
