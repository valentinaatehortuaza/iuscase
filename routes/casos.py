import os
import traceback
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup
from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
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
from services.catalogo_derechos import CATALOGO as CATALOGO_DERECHOS, codificar as codificar_derechos, decodificar as decodificar_derechos, nombre_derecho
from services.categorias_elementos import nombre_categoria
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

        # Etapas 0 a 2: clasificacion, nucleo narrativo y preguntas guia.
        # Las 4 llamadas van en un solo try/except: si la sentencia subida es
        # muy larga/compleja o hay un problema temporal con la IA, el
        # estudiante ve un mensaje claro en vez de un error generico, y puede
        # volver a intentar sin perder lo que ya escribio en el formulario.
        try:
            clasificacion = servicio_ia.clasificar_sentencia(texto)
            exposicion = servicio_ia.generar_nucleo_narrativo(texto, clasificacion)

            # Preguntas guia, en llamadas separadas por capa (cada una con su
            # propio bloque de "hechos relevantes" - Nivel B) para que
            # ninguna llamada individual a la IA tenga que generar demasiado
            # contenido de una sola vez.
            preguntas_capa1 = servicio_ia.generar_preguntas_capa1(
                texto, clasificacion, exposicion.get("nucleo_narrativo")
            )
            preguntas_capa2 = servicio_ia.generar_preguntas_capa2(
                texto, clasificacion, exposicion.get("nucleo_narrativo")
            )
        except Exception:
            traceback.print_exc()
            # Descartamos los tokens de este intento fallido por la misma
            # razon que en resolver_caso: servicio_ia es una sola instancia
            # compartida y si no se drena aqui, quedan pegados en el contador.
            servicio_ia.obtener_y_reiniciar_uso()
            flash(
                "Hubo un problema generando las preguntas para esta sentencia "
                "(puede ser un problema temporal de conexion con la IA, o que "
                "la sentencia sea mas larga o compleja de lo esperado). Intenta "
                "subirla de nuevo en un momento."
            )
            return redirect(url_for("casos.subir_sentencia"))

        tokens_entrada, tokens_salida = servicio_ia.obtener_y_reiniciar_uso()

        caso = CasoEstudio(
            usuario_id=session["usuario_id"],
            sentencia_id=sentencia.id,
            tipo_tutela=clasificacion.get("tipo_tutela"),
            fundamento_particular=clasificacion.get("fundamento_particular"),
            requiere_ponderacion=bool(clasificacion.get("requiere_ponderacion")),
            legitimacion_activa_especial=clasificacion.get("legitimacion_activa_especial"),
            derechos_vulnerados=codificar_derechos(clasificacion.get("derechos_vulnerados")),
            nucleo_narrativo=exposicion.get("nucleo_narrativo"),
            problema_juridico=exposicion.get("problema_juridico"),
            tokens_entrada=tokens_entrada,
            tokens_salida=tokens_salida,
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
        # Etapa 3: se guardan (o actualizan, si ya existian de un intento
        # anterior que no llego a completarse) las respuestas del estudiante
        paquete_para_ia = []
        for pregunta in preguntas_ordenadas:
            texto_respuesta = request.form.get(f"respuesta_{pregunta.id}", "").strip()
            if pregunta.respuesta:
                pregunta.respuesta.texto = texto_respuesta
                pregunta.respuesta.fecha = datetime.utcnow()
            else:
                db.session.add(Respuesta(pregunta_id=pregunta.id, texto=texto_respuesta))
            paquete_para_ia.append({
                "pregunta": pregunta.enunciado,
                "hechos_relevantes": pregunta.hechos_relevantes,
                "respuesta_estudiante": texto_respuesta,
            })
        db.session.commit()

        # Etapa 4: contraste y diagnostico, elemento por elemento. Si la IA
        # falla aqui (ej. problema de conexion), las respuestas ya quedaron
        # guardadas arriba -- el estudiante no pierde lo que escribio y puede
        # reintentar sin volver a escribir nada.
        try:
            diagnostico = servicio_ia.generar_diagnostico(caso.sentencia.texto, paquete_para_ia)
            tokens_entrada, tokens_salida = servicio_ia.obtener_y_reiniciar_uso()
        except Exception:
            traceback.print_exc()
            # Descartamos los tokens que alcanzo a consumir este intento
            # fallido para que NO se le sumen por error al proximo caso que
            # si se complete (servicio_ia es una sola instancia compartida
            # por toda la app, asi que si no se drena aqui quedan pegados
            # en el contador hasta la siguiente llamada exitosa).
            servicio_ia.obtener_y_reiniciar_uso()
            flash(
                "Tus respuestas quedaron guardadas. Hubo un problema generando el "
                "diagnóstico (puede ser un problema temporal de conexión con la IA); "
                "intenta enviar de nuevo en un momento."
            )
            return redirect(url_for("casos.resolver_caso", caso_id=caso.id))

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

        calidad_sustento = diagnostico.get("calidad_sustento") or {}
        caso.calidad_sustento_nivel = calidad_sustento.get("nivel")
        caso.calidad_sustento_justificacion = calidad_sustento.get("justificacion")

        caso.tokens_entrada = (caso.tokens_entrada or 0) + tokens_entrada
        caso.tokens_salida = (caso.tokens_salida or 0) + tokens_salida
        caso.estado = "completado"
        caso.fecha_completado = datetime.utcnow()
        db.session.commit()

        return redirect(url_for("casos.ver_retroalimentacion", caso_id=caso.id))

    return render_template("resolver_caso.html", caso=caso, preguntas=preguntas_ordenadas)


@casos_bp.route("/caso/<int:caso_id>/guardar-borrador", methods=["POST"])
@login_requerido
def guardar_borrador(caso_id):
    """Guardado temporal: guarda lo que el estudiante lleva escrito sin
    exigir que todas las preguntas esten respondidas y sin disparar el
    diagnostico de IA. Pensado para no perder avance si cierra o recarga
    la pagina a mitad de camino."""
    caso = CasoEstudio.query.filter_by(
        id=caso_id, usuario_id=session["usuario_id"]
    ).first_or_404()

    if caso.estado == "completado":
        return jsonify({"ok": False, "error": "Este caso ya fue completado."}), 400

    preguntas_ordenadas = sorted(caso.preguntas, key=lambda p: p.orden or 0)
    for pregunta in preguntas_ordenadas:
        texto_respuesta = request.form.get(f"respuesta_{pregunta.id}", "").strip()
        if pregunta.respuesta:
            pregunta.respuesta.texto = texto_respuesta
            pregunta.respuesta.fecha = datetime.utcnow()
        else:
            db.session.add(Respuesta(pregunta_id=pregunta.id, texto=texto_respuesta))
    db.session.commit()

    # Colombia es UTC-5 todo el año (no tiene horario de verano), asi que un
    # desplazamiento fijo es correcto y no depende de que el servidor tenga
    # instalada la base de datos de zonas horarias (tzdata).
    hora_colombia = datetime.utcnow() - timedelta(hours=5)
    return jsonify({"ok": True, "hora": hora_colombia.strftime("%H:%M")})


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


@casos_bp.route("/progreso")
@login_requerido
def progreso():
    casos = (
        CasoEstudio.query
        .filter_by(usuario_id=session["usuario_id"])
        .order_by(CasoEstudio.fecha_creacion.asc())
        .all()
    )

    # Ordenados por cuando se COMPLETARON (no por cuando se crearon): un caso
    # puede quedar "en progreso" dias y terminarse despues de otros casos
    # creados mas tarde -- "tu caso mas reciente" en esta pagina debe ser el
    # ultimo que de verdad terminaste, no el ultimo que empezaste. Los casos
    # completados antes de que existiera fecha_completado caen al final segun
    # su fecha_creacion como respaldo.
    completados = sorted(
        (c for c in casos if c.estado == "completado" and c.porcentaje_global is not None),
        key=lambda c: c.fecha_completado or c.fecha_creacion or datetime.min,
    )

    # ---- serie para la linea de evolucion del puntaje ----
    puntos_linea = []
    if len(completados) >= 3:
        x_ini, x_fin = 70, 620
        y_arriba, y_abajo = 20, 200
        n = len(completados)
        for i, c in enumerate(completados):
            x = x_ini if n == 1 else x_ini + (x_fin - x_ini) * i / (n - 1)
            y = y_abajo - (c.porcentaje_global / 100) * (y_abajo - y_arriba)
            puntos_linea.append({
                "x": round(x, 1),
                "y": round(y, 1),
                "valor": c.porcentaje_global,
                "fecha": c.fecha_creacion.strftime("%-d %b").lower() if c.fecha_creacion else "",
                "titulo": c.sentencia.titulo if c.sentencia else f"Caso {c.id}",
            })
    polyline_puntos = " ".join(f"{p['x']},{p['y']}" for p in puntos_linea)

    promedio_puntaje = (
        round(sum(c.porcentaje_global for c in completados) / len(completados), 1)
        if completados else None
    )
    # Comparado contra el caso inmediatamente anterior (no contra el primero):
    # con el primero, el indicador se puede quedar en +0.0% aunque hayas
    # mejorado y luego bajado otra vez -- lo que de verdad responde "¿mejore
    # desde la ultima vez?" es el delta contra el caso justo antes del actual.
    delta_vs_anterior = None
    if len(completados) >= 2:
        delta_vs_anterior = round(
            completados[-1].porcentaje_global - completados[-2].porcentaje_global, 1
        )

    # ---- fortalezas y debilidades por categoria fija (capa + orden, no el texto libre de la IA) ----
    conteos = {}
    for caso in casos:
        # Pregunta.orden es un consecutivo GLOBAL para todo el caso (1,2,3...
        # sin reiniciarse al pasar de la capa 1 a la capa 2) -- asi se le
        # muestran las preguntas al estudiante en resolver_caso.html. Pero
        # nombre_categoria() espera la posicion de la pregunta DENTRO de su
        # propia capa (1,2,3... reiniciando en cada capa), que es como estan
        # armados los mapas CAPA_1 / CAPA_2_* en categorias_elementos.py. Si
        # se le pasa el orden global tal cual, las preguntas de la capa 2 (y
        # a veces de la capa 1) quedan mal etiquetadas o se pierden de la
        # cuenta -- por eso aqui se recalcula la posicion relativa a su capa
        # antes de llamar a nombre_categoria().
        orden_en_capa_por_pregunta = {}
        contador_capa = {}
        for p in sorted(caso.preguntas, key=lambda p: p.orden or 0):
            contador_capa[p.capa] = contador_capa.get(p.capa, 0) + 1
            orden_en_capa_por_pregunta[p.id] = contador_capa[p.capa]

        for diag in caso.diagnostico_elementos:
            pregunta = diag.pregunta
            if not pregunta or diag.veredicto == "no_aplicable" or diag.puntos is None:
                continue
            orden_en_capa = orden_en_capa_por_pregunta.get(pregunta.id)
            categoria = nombre_categoria(
                caso.tipo_tutela, pregunta.capa, orden_en_capa, caso.requiere_ponderacion
            )
            if not categoria:
                continue
            c = conteos.setdefault(
                categoria, {"acertado": 0, "incompleto": 0, "incorrecto": 0, "suma_puntos": 0.0, "total": 0}
            )
            if diag.veredicto in ("acertado", "incompleto", "incorrecto"):
                c[diag.veredicto] += 1
            c["suma_puntos"] += diag.puntos
            c["total"] += 1

    barras = []
    for categoria, c in conteos.items():
        if c["total"] == 0:
            continue
        barras.append({
            "categoria": categoria,
            "porcentaje": round(c["suma_puntos"] / c["total"] * 100, 1),
            "acertado": c["acertado"],
            "incompleto": c["incompleto"],
            "incorrecto": c["incorrecto"],
            "total": c["total"],
        })
    barras.sort(key=lambda b: b["porcentaje"], reverse=True)

    for b in barras:
        if b["porcentaje"] >= 70:
            b["nivel"] = "alto"
        elif b["porcentaje"] >= 40:
            b["nivel"] = "medio"
        else:
            b["nivel"] = "bajo"

    categoria_mas_debil = barras[-1] if barras else None

    # ---- fortalezas y debilidades por area del derecho (catalogo fijo, multi-etiqueta) ----
    conteos_derecho = {}
    for caso in completados:
        for slug in decodificar_derechos(caso.derechos_vulnerados):
            c = conteos_derecho.setdefault(slug, {"suma_porcentaje": 0.0, "total": 0, "titulos": []})
            c["suma_porcentaje"] += caso.porcentaje_global
            c["total"] += 1
            c["titulos"].append(caso.sentencia.titulo if caso.sentencia else f"Caso {caso.id}")

    barras_derecho = []
    for slug, c in conteos_derecho.items():
        if c["total"] == 0:
            continue
        barras_derecho.append({
            "categoria": nombre_derecho(slug),
            # "otro" es el cajon de sastre del catalogo fijo (ver
            # services/catalogo_derechos.py): un caso cae aqui cuando su
            # derecho principal no es ninguno de los 8 mas comunes del
            # catalogo (ej. derecho de peticion, que se excluyo a proposito
            # por no ser tipicamente el derecho sustantivo del caso). Sin
            # mas contexto "Otro" no dice nada util, por eso se guardan los
            # titulos de los casos detras de esa etiqueta.
            "slug": slug,
            "porcentaje": round(c["suma_porcentaje"] / c["total"], 1),
            "total": c["total"],
            "titulos": c["titulos"],
        })
    barras_derecho.sort(key=lambda b: b["porcentaje"], reverse=True)

    for b in barras_derecho:
        if b["porcentaje"] >= 70:
            b["nivel"] = "alto"
        elif b["porcentaje"] >= 40:
            b["nivel"] = "medio"
        else:
            b["nivel"] = "bajo"

    derecho_mas_debil = barras_derecho[-1] if barras_derecho else None

    # ---- calidad de sustento y redaccion (holistico por caso) ----
    casos_con_sustento = [c for c in completados if c.calidad_sustento_nivel]
    conteo_sustento = {"alta": 0, "media": 0, "baja": 0}
    for c in casos_con_sustento:
        if c.calidad_sustento_nivel in conteo_sustento:
            conteo_sustento[c.calidad_sustento_nivel] += 1
    ultimo_sustento = casos_con_sustento[-1] if casos_con_sustento else None

    return render_template(
        "progreso.html",
        puntos_linea=puntos_linea,
        polyline_puntos=polyline_puntos,
        total_completados=len(completados),
        promedio_puntaje=promedio_puntaje,
        delta_vs_anterior=delta_vs_anterior,
        barras=barras,
        categoria_mas_debil=categoria_mas_debil,
        barras_derecho=barras_derecho,
        derecho_mas_debil=derecho_mas_debil,
        conteo_sustento=conteo_sustento,
        total_con_sustento=len(casos_con_sustento),
        ultimo_sustento=ultimo_sustento,
    )
