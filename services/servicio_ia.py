import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")


class ServicioIA:
    """
    Orquesta el flujo de estudio de casos usando la API de Anthropic (Claude).

    Requiere la variable de entorno ANTHROPIC_API_KEY. Crea un archivo .env
    en la raiz del proyecto (no lo subas a git) con:
        ANTHROPIC_API_KEY=tu_clave_aqui
    """

    def __init__(self):
        self._cliente = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # ---------- utilidades internas ----------

    def _preguntar(self, system, prompt, max_tokens=1500):
        respuesta = self._cliente.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        if respuesta.stop_reason == "max_tokens":
            raise ValueError(
                "La respuesta de la IA se corto porque supero el limite de "
                f"max_tokens={max_tokens} para este paso. Sube ese limite en "
                "servicio_ia.py (el caso es mas largo/complejo de lo esperado)."
            )

        # La respuesta puede incluir bloques de "pensamiento" (thinking) antes
        # del bloque de texto real, asi que buscamos especificamente el/los
        # bloques de tipo "text" en vez de asumir que content[0] es el texto.
        bloques_texto = [
            bloque.text for bloque in respuesta.content if bloque.type == "text"
        ]
        if not bloques_texto:
            raise ValueError("La IA no devolvio ningun bloque de texto en la respuesta.")
        return "".join(bloques_texto)

    def _parsear_json(self, texto):
        """Extrae el primer bloque JSON de la respuesta del modelo."""
        inicio = texto.find("{")
        fin = texto.rfind("}")
        if inicio == -1 or fin == -1:
            raise ValueError(f"La IA no devolvio JSON valido:\n{texto}")
        return json.loads(texto[inicio:fin + 1])

    # ---------- paso 2: comprimir el problema juridico ----------

    def analizar_sentencia(self, texto_sentencia):
        """Comprime la sentencia en su problema juridico central."""
        system = (
            "Eres un profesor de derecho que ayuda a estudiantes a identificar "
            "el problema juridico central de una sentencia. Responde siempre "
            "en JSON valido, sin texto adicional."
        )
        prompt = f"""Lee la siguiente sentencia y responde en JSON con esta forma exacta:

{{
  "problema_juridico": "una sola pregunta juridica clara que resume el caso",
  "tribunal": "tribunal que emitio la sentencia, si se identifica",
  "fecha": "fecha de la sentencia si se identifica (YYYY-MM-DD o null)"
}}

SENTENCIA:
{texto_sentencia}
"""
        return self._parsear_json(self._preguntar(system, prompt))

    # ---------- paso 3: explicar el caso ----------

    def generar_caso(self, texto_sentencia, problema_juridico):
        """Explica el caso al estudiante: hechos, actores y elementos clave."""
        system = (
            "Eres un profesor de derecho que explica casos a estudiantes de "
            "forma clara y pedagogica, sin revelar todavia la decision del "
            "juez. Responde siempre en JSON valido, sin texto adicional."
        )
        prompt = f"""Problema juridico: {problema_juridico}

A partir de la siguiente sentencia, construye el material de estudio para
un estudiante que aun no conoce el fallo. Responde en JSON:

{{
  "hechos": "narracion clara y neutral de los hechos relevantes",
  "actores": ["lista de las partes/actores involucrados y su rol"],
  "elementos_clave": ["conceptos o normas que el estudiante debe tener en cuenta"],
  "contexto": "contexto juridico o social relevante para entender el caso"
}}

No incluyas la decision del juez ni el resultado del fallo.

SENTENCIA:
{texto_sentencia}
"""
        return self._parsear_json(self._preguntar(system, prompt, max_tokens=4000))

    # ---------- paso 4: preguntas guia ----------

    def generar_preguntas(self, caso_estudio):
        """Genera preguntas guia para que el estudiante construya su analisis."""
        system = (
            "Eres un profesor de derecho que usa el metodo socratico: haces "
            "preguntas que guian al estudiante a razonar, sin darle la "
            "respuesta. Responde siempre en JSON valido, sin texto adicional."
        )
        prompt = f"""Caso de estudio:
Hechos: {caso_estudio.hechos}
Contexto: {caso_estudio.contexto}
Problema juridico: {caso_estudio.problema_juridico}

Genera entre 3 y 5 preguntas guia, en orden logico, que ayuden al
estudiante a construir su propio analisis (normas aplicables,
consideraciones particulares, argumentos, posible decision). La ULTIMA
pregunta debe tener tipo "decision" y pedirle al estudiante que proponga
su propia decision razonada para el caso. Responde en
JSON:

{{
  "preguntas": [
    {{"enunciado": "...", "tipo": "normas|argumentos|decision|otro", "orden": 1}}
  ]
}}
"""
        return self._parsear_json(self._preguntar(system, prompt, max_tokens=2000))["preguntas"]

    # ---------- evaluacion incremental (opcional, por pregunta) ----------

    def evaluar_respuesta(self, pregunta, respuesta):
        """Da una senal rapida de si una respuesta puntual esta encaminada."""
        system = (
            "Eres un profesor de derecho dando retroalimentacion breve e "
            "incremental. Responde siempre en JSON valido, sin texto adicional."
        )
        prompt = f"""Pregunta: {pregunta.enunciado}
Respuesta del estudiante: {respuesta.texto}

Responde en JSON:
{{
  "encaminada": true o false,
  "comentario_breve": "una frase de orientacion, sin dar la respuesta completa"
}}
"""
        return self._parsear_json(self._preguntar(system, prompt, max_tokens=400))

    # ---------- extraer la decision real (no se muestra al estudiante todavia) ----------

    def extraer_decision_judicial(self, texto_sentencia):
        """Extrae la decision real del juez, sus fundamentos y el resultado."""
        system = (
            "Eres un asistente juridico que extrae con precision la decision "
            "final de una sentencia. Responde siempre en JSON valido, sin "
            "texto adicional."
        )
        prompt = f"""Lee la siguiente sentencia y extrae la decision real del juez.
Responde en JSON:

{{
  "decision": "que decidio el juez, en una o dos frases",
  "fundamentos": "los fundamentos juridicos principales de esa decision",
  "resultado": "el resultado practico para las partes (gano, perdio, se ordeno que...)"
}}

SENTENCIA:
{texto_sentencia}
"""
        return self._parsear_json(self._preguntar(system, prompt, max_tokens=2000))

    # ---------- paso 6: comparar con la decision real ----------

    def comparar_decision(self, analisis, decision_judicial):
        """Compara el analisis del estudiante con la decision real del juez."""
        system = (
            "Eres un profesor de derecho evaluando el analisis de un "
            "estudiante frente al fallo real. Se riguroso pero constructivo. "
            "Responde siempre en JSON valido, sin texto adicional."
        )
        prompt = f"""ANALISIS DEL ESTUDIANTE:
Problema juridico identificado: {analisis.problema_juridico_estudiante}
Normas citadas: {analisis.normas}
Argumentos: {analisis.argumentos}
Decision propuesta: {analisis.decision_estudiante}

DECISION REAL DEL JUEZ:
Decision: {decision_judicial.decision}
Fundamentos: {decision_judicial.fundamentos}
Resultado: {decision_judicial.resultado}

Responde en JSON:
{{
  "coherencia": "alta|media|baja",
  "coincide_con_el_fallo": true o false,
  "diferencias_clave": ["..."],
  "normas_omitidas": ["normas relevantes que el estudiante no menciono"]
}}
"""
        return self._parsear_json(self._preguntar(system, prompt, max_tokens=2000))

    # ---------- retroalimentacion final ----------

    def generar_retroalimentacion(self, comparacion):
        """Convierte la comparacion en retroalimentacion pedagogica final."""
        system = (
            "Eres un profesor de derecho dando retroalimentacion final a un "
            "estudiante. Se constructivo: reconoce fortalezas antes de "
            "senalar debilidades. Responde siempre en JSON valido, sin texto "
            "adicional."
        )
        prompt = f"""Resultado de la comparacion entre el analisis del estudiante y el fallo real:
{json.dumps(comparacion, ensure_ascii=False, indent=2)}

Responde en JSON:
{{
  "coherencia": "alta|media|baja",
  "fortalezas": "2-3 frases sobre lo que el estudiante hizo bien",
  "debilidades": "2-3 frases sobre lo que le hizo falta",
  "sugerencias": "2-3 frases con consejos concretos para mejorar",
  "resultado": "resumen de una frase del veredicto de este analisis"
}}
"""
        return self._parsear_json(self._preguntar(system, prompt, max_tokens=2000))
