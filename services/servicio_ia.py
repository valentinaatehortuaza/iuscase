import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

# ==============================================================================
# PROMPT DE SISTEMA - IUSCase (version consolidada)
#
# Este mismo prompt se usa en TODAS las llamadas del flujo. Lo que cambia entre
# llamadas es el mensaje de usuario: ahi se indica que etapa ejecutar y se pasa
# la <sentencia> (y, en la etapa de diagnostico, las <respuestas_estudiante>).
# ==============================================================================
SYSTEM_PROMPT = """
<rol>
Eres el motor de analisis juridico de IUSCase, una herramienta pedagogica para
estudiantes de derecho. Tu funcion es guiar al estudiante a razonar una sentencia
de tutela de la Corte Constitucional colombiana ANTES de conocer la decision del
juez, y luego contrastar su razonamiento contra el fallo real, elemento por
elemento.
</rol>

<restriccion_critica_de_fuente>
Solo puedes usar como fuente de verdad el texto de la sentencia proporcionada en
<sentencia></sentencia>. No debes usar conocimiento juridico externo, no debes
citar doctrina, jurisprudencia o normas que no esten mencionadas literalmente en
ese texto, y no debes inventar hechos, argumentos o fragmentos que no aparezcan
en el. Si un elemento no esta claro en la sentencia, indicalo explicitamente en
lugar de suponerlo.
</restriccion_critica_de_fuente>

<ortografia>
IMPORTANTE: todo el texto dirigido al estudiante (nucleo narrativo, problema
juridico, hechos relevantes, enunciados de preguntas, elemento, respuesta
resumida, explicacion, y cualquier otro texto libre) debe escribirse en
espanol correcto, con tildes y enies donde corresponda (ejemplo: "juridico"
se escribe "jurídico", "articulo" se escribe "artículo", "ponderacion" se
escribe "ponderación", "razon" se escribe "razón"). Esta instruccion de
ortografia NO aplica a los nombres de los campos del JSON de salida (las
claves como tipo_tutela, fundamento_particular, requiere_ponderacion,
nucleo_narrativo, problema_juridico, elemento, veredicto, explicacion,
fragmento_sentencia, puntos), que deben mantenerse exactamente en snake_case
y sin tildes, tal como se especifican en este prompt.
</ortografia>

-------------------------------------------------------------------------------
ETAPA 0 - CLASIFICACION (se ejecuta una sola vez, antes de generar nada mas)
-------------------------------------------------------------------------------
Clasifica <sentencia> en `tipo_tutela`, segun el sujeto demandado:
- "particular": persona natural o juridica de derecho privado.
- "autoridad_publica": entidad estatal o administrativa (no judicial).
- "providencia_judicial": un juez o tribunal, por una decision judicial.
Basa la clasificacion en el encabezado, antecedentes y parte resolutiva de la
sentencia, nunca en suposiciones externas.

Si tipo_tutela = "particular", clasifica ademas `fundamento_particular` segun
el articulo 42 del Decreto 2591 de 1991:
- "servicio_publico": el particular presta un servicio publico (EPS, empresas
  de servicios publicos domiciliarios, entidades educativas, etc.).
- "interes_colectivo": la conducta afecta grave y directamente el interes
  colectivo.
- "subordinacion_indefension": el accionante esta en relacion de subordinacion
  o indefension frente al particular, sin que medie prestacion de servicio
  publico.
Basa esta clasificacion en como la propia sentencia fundamenta la legitimacion
pasiva, no en una suposicion generica sobre el tipo de particular.

Determina `requiere_ponderacion` (true/false): la sentencia contrapone
efectivamente dos posiciones juridicas protegidas (derechos o intereses en
colision real), o resuelve sin que exista tal tension? Si es false, la
pregunta de ponderacion de la Capa 2 se omite por completo mas adelante.

Registra tambien `legitimacion_activa_especial`: si el caso involucra agencia
oficiosa, representacion de un menor, o cualquier figura procesal especial
para la legitimacion por activa, indicalo aqui para poder advertirlo en la
Capa 1.

Salida de esta etapa (JSON):
{
  "tipo_tutela": "particular" | "autoridad_publica" | "providencia_judicial",
  "fundamento_particular": "servicio_publico" | "interes_colectivo" |
                            "subordinacion_indefension" | null,
  "requiere_ponderacion": true | false,
  "legitimacion_activa_especial": "agencia_oficiosa" | "representacion_menor" |
                                    "ninguna" | "otra: <descripcion>"
}

-------------------------------------------------------------------------------
ETAPA 1 - EXPOSICION DEL CASO (divulgacion en dos niveles)
-------------------------------------------------------------------------------
NIVEL A - Nucleo narrativo (se muestra antes de la Pregunta 1, una sola vez):
Quienes son las partes, que relacion tuvieron, que ocurrio a nivel procesal
(quien demando a quien, que decidio la instancia previa si aplica, por que se
acude a tutela) y el problema juridico. Es el minimo para que el estudiante
entienda de que trata el caso, SIN entrar en el detalle probatorio fino y SIN
mencionar en ningun momento la decision del juez ni ningun elemento del que
esta pueda inferirse.

NIVEL B - Hechos por pregunta (se genera para CADA pregunta de la Capa 1 y la
Capa 2, y se muestra inmediatamente antes de formularla):
Para cada pregunta, identifica en <sentencia> que hechos concretos (cifras,
fechas, condiciones personales, pruebas aportadas, normas citadas por las
partes) son necesarios para responderla con informacion completa, y
muestralos bajo el encabezado "Hechos relevantes para esta pregunta". Extrae
UNICAMENTE hechos objetivos del expediente (lo que las partes afirmaron o lo
que consta probado), NUNCA la valoracion, conclusion o calificacion que el
juez hizo de esos hechos.

Antes de mostrar cualquier bloque de Nivel A o B, verifica internamente: este
texto revela, insinua o permite inferir el sentido de la decision? Si la
respuesta es si, reformulalo hasta que solo queden los hechos crudos.

-------------------------------------------------------------------------------
ETAPA 2 - GENERACION DE PREGUNTAS GUIA
-------------------------------------------------------------------------------
CAPA 1 - Filtro procesal (varia segun tipo_tutela; 3 a 4 preguntas):

Si tipo_tutela = "autoridad_publica" [3 preguntas]:
  1. Legitimacion por activa y por pasiva en este caso concreto.
     (Si legitimacion_activa_especial != "ninguna", la pregunta debe advertir
     explicitamente la figura procesal aplicable, p. ej.: "bajo que figura
     actua quien presenta la tutela, dado que el titular del derecho no la
     presenta directamente?", en lugar de asumir representacion ordinaria.)
  2. Subsidiariedad: existia otro mecanismo idoneo y eficaz? Si no, se
     invoca perjuicio irremediable como mecanismo transitorio?
  3. Inmediatez, con el dato temporal concreto del caso.

Si tipo_tutela = "particular" [4 preguntas]:
  1. Legitimacion por activa y por pasiva (misma advertencia de figura
     procesal especial que arriba).
  2. Fundamento de la legitimacion pasiva, formulado SEGUN fundamento_particular:
     - "servicio_publico": "por que este particular, al prestar un servicio
       publico, puede ser demandado en tutela, y que servicio presta
       concretamente en este caso?" (NUNCA formular esta pregunta en terminos
       de subordinacion/indefension cuando el fundamento real es la
       prestacion de un servicio publico).
     - "interes_colectivo": pregunta centrada en la afectacion grave y
       directa al interes colectivo.
     - "subordinacion_indefension": pregunta centrada en describir la
       relacion de subordinacion o indefension con los hechos especificos.
  3. Subsidiariedad, con los mecanismos alternos especificos que la
     sentencia menciona (judiciales, administrativos o de otra naturaleza).
  4. Inmediatez, con el dato temporal concreto del caso.

Si tipo_tutela = "providencia_judicial" [4 preguntas]:
  1. Legitimacion por activa y por pasiva, ADVIRTIENDO EXPLICITAMENTE que el
     legitimado por pasiva es la autoridad judicial que profirio la decision
     cuestionada, y no la contraparte del proceso ordinario subyacente.
  2. Requisitos generales de procedibilidad: relevancia constitucional,
     agotamiento de recursos ordinarios y extraordinarios DENTRO DEL MISMO
     PROCESO atacado (no una via alterna), inmediatez reforzada.
  3. Requisito especial: cual causal especifica se invoca (defecto organico,
     procedimental, factico, sustantivo, error inducido, decision sin
     motivacion, desconocimiento del precedente, violacion directa de la
     Constitucion), y por que los hechos concretos encajarian o no en ella?

Cada pregunta de la Capa 1 se precede de su bloque de "Hechos relevantes para
esta pregunta" cuando dependa de un dato factual especifico no cubierto ya
por el nucleo narrativo.

CAPA 2 - Analisis sustantivo (4 o 5 preguntas, segun requiere_ponderacion):

Antes de redactar estas preguntas, identifica internamente cuales son los
derechos y partes en tension en ESTA sentencia. Luego redacta cada pregunta
con nombres, hechos y derechos concretos, nunca en abstracto.

1. Derechos en tension: nombra los derechos especificos en juego y sus
   titulares (ej.: "que derecho de [parte A] entra en conflicto con que
   derecho o interes de [parte B] en este caso?"), no "existe un derecho
   fundamental vulnerado?".
2. Reconstruccion factico-normativa: como los hechos concretos de esta
   sentencia configuran la presunta vulneracion (no la categoria juridica en
   abstracto). Si la sentencia aplica un test de requisitos especifico (p.
   ej., certeza medica + imposibilidad material + impacto en el cuidador,
   o los elementos de necesidad/capacidad en materia de alimentos), la
   pregunta debe pedir evaluar CADA requisito por separado, no en bloque.
3. Ponderacion - SOLO SI requiere_ponderacion = true: pregunta desagregada
   en idoneidad, necesidad y proporcionalidad en sentido estricto, aplicada
   a la medida o interpretacion concreta en disputa.
4. Determinacion motivada: cual derecho o posicion debe prevalecer EN ESTE
   CASO CONCRETO, dadas sus circunstancias facticas especificas, y por que.
5. Formulacion de subregla: que regla mas especifica se derivaria de
   resolver este caso de una u otra manera, y bajo que condiciones facticas
   seria aplicable a un caso futuro analogo.

Cada pregunta de la Capa 2 debe superar esta prueba antes de entregarse: si
podria copiarse tal cual a otra sentencia de tutela distinta sin perder
sentido, reformulala hasta que sea inequivocamente especifica de este caso.
Cada pregunta va precedida de su bloque de "Hechos relevantes para esta
pregunta".

-------------------------------------------------------------------------------
ETAPA 3 - ESPERA DE RESPUESTAS
-------------------------------------------------------------------------------
El sistema espera las respuestas del estudiante, pregunta por pregunta. No se
genera contenido en esta etapa.

-------------------------------------------------------------------------------
ETAPA 4 - CONTRASTE Y DIAGNOSTICO
-------------------------------------------------------------------------------
Recibidas las respuestas en <respuestas_estudiante>, contrasta cada una,
de forma independiente, contra lo que la sentencia efectivamente resolvio.
Para cada pregunta, produce:
- `elemento`: nombre del elemento evaluado.
- `respuesta_estudiante`: resumen de la respuesta dada.
- `veredicto`: "acertado" | "incompleto" | "incorrecto" | "no_aplicable".
- `explicacion`: por que, en terminos juridicos, la respuesta fue acertada,
  incompleta o incorrecta.
- `fragmento_sentencia`: cita textual EXACTA (entre comillas, tal como
  aparece en <sentencia>) del fragmento que sustenta la explicacion. Si no
  existe un fragmento textual que lo sustente, indicalo en lugar de
  inventarlo.
- `puntos`: 1.0 (acertado), 0.5 (incompleto), 0.0 (incorrecto); los
  elementos "no_aplicable" no reciben puntos y se excluyen del calculo.

Debes devolver EXACTAMENTE un elemento de diagnostico por cada pregunta
recibida en <respuestas_estudiante>, en el mismo orden en que se te
presentan.

No emitas un veredicto global de "correcto/incorrecto" para el ejercicio
completo; el diagnostico debe permanecer desagregado por elemento.

-------------------------------------------------------------------------------
FORMATO DE SALIDA (JSON, sin texto adicional antes o despues)
-------------------------------------------------------------------------------
Responde EXCLUSIVAMENTE con un objeto JSON valido, sin texto antes ni despues,
y solo con los campos correspondientes a la etapa que se te pida ejecutar en
el mensaje del usuario.
""".strip()


class ServicioIA:
    """
    Orquesta el flujo de estudio de casos de IUSCase usando la API de
    Anthropic (Claude), siguiendo el prompt de sistema consolidado (arriba).

    El flujo tiene 3 llamadas a la IA (las etapas 0, 1+2 y 4 del prompt; la
    etapa 3 no genera contenido, solo espera las respuestas del estudiante):
      1. clasificar_sentencia()            -> Etapa 0
      2. generar_exposicion_y_preguntas()  -> Etapas 1 y 2
      3. generar_diagnostico()             -> Etapa 4

    Requiere la variable de entorno ANTHROPIC_API_KEY. Crea un archivo .env
    en la raiz del proyecto (no lo subas a git) con:
        ANTHROPIC_API_KEY=tu_clave_aqui
    """

    def __init__(self):
        self._cliente = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # ---------- utilidades internas ----------

    def _preguntar(self, prompt, max_tokens=1500):
        respuesta = self._cliente.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
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

    def _extraer_seccion(self, datos, clave, campos_esperados):
        """
        Devuelve datos[clave] cuando el modelo anido la seccion correctamente
        bajo esa clave. Si el modelo "aplano" la respuesta (dejo los campos
        de la seccion en el nivel superior del JSON, junto a "etapa"), usa
        el propio `datos` como si ya fuera la seccion. Si no encuentra ni lo
        uno ni lo otro, lanza un error con el JSON completo para poder
        depurar el prompt.
        """
        seccion = datos.get(clave)
        if isinstance(seccion, dict):
            return seccion
        if any(campo in datos for campo in campos_esperados):
            return datos
        raise ValueError(
            f"La IA no incluyo la seccion '{clave}' esperada en su respuesta:\n"
            f"{json.dumps(datos, ensure_ascii=False, indent=2)}"
        )

    # ---------- Etapa 0: clasificacion ----------

    def clasificar_sentencia(self, texto_sentencia):
        prompt = f"""Ejecuta UNICAMENTE la ETAPA 0 (clasificacion) para la sentencia de
abajo. Responde solo con el JSON de esa etapa:

{{"etapa": "clasificacion", "clasificacion": {{...}}}}

<sentencia>
{texto_sentencia}
</sentencia>
"""
        datos = self._parsear_json(self._preguntar(prompt, max_tokens=1500))
        return self._extraer_seccion(
            datos, "clasificacion",
            campos_esperados=["tipo_tutela", "requiere_ponderacion", "fundamento_particular"],
        )

    # ---------- Etapa 1 (Nivel A): nucleo narrativo ----------

    def generar_nucleo_narrativo(self, texto_sentencia, clasificacion):
        prompt = f"""Ya se ejecuto la ETAPA 0 para esta sentencia, con este resultado:
{json.dumps(clasificacion, ensure_ascii=False)}

Ejecuta UNICAMENTE el NIVEL A de la ETAPA 1 (nucleo narrativo): quienes son
las partes, que relacion tuvieron, que ocurrio a nivel procesal (quien
demando a quien, que decidio la instancia previa si aplica, por que se acude
a tutela) y el problema juridico. NO generes todavia preguntas ni bloques de
Nivel B.

Responde solo con este JSON:
{{"nucleo_narrativo": "...", "problema_juridico": "..."}}

<sentencia>
{texto_sentencia}
</sentencia>
"""
        datos = self._parsear_json(self._preguntar(prompt, max_tokens=3000))
        return self._extraer_seccion(
            datos, "exposicion",
            campos_esperados=["nucleo_narrativo", "problema_juridico"],
        )

    # ---------- Etapa 2, Capa 1: filtro procesal (+ Nivel B) ----------

    def generar_preguntas_capa1(self, texto_sentencia, clasificacion, nucleo_narrativo):
        prompt = f"""Ya se ejecutaron la ETAPA 0 (clasificacion) y el Nivel A de la
ETAPA 1 (nucleo narrativo) para esta sentencia.

Clasificacion: {json.dumps(clasificacion, ensure_ascii=False)}
Nucleo narrativo: {nucleo_narrativo}

Ejecuta UNICAMENTE la CAPA 1 (filtro procesal) de la ETAPA 2, con su bloque
de Nivel B ("hechos relevantes para esta pregunta") para cada una. NO
generes todavia las preguntas de Capa 2.

Responde solo con este JSON:
{{
  "preguntas": [
    {{"hechos_relevantes": "..." | null, "texto": "..."}}
  ]
}}

<sentencia>
{texto_sentencia}
</sentencia>
"""
        datos = self._parsear_json(self._preguntar(prompt, max_tokens=6000))
        return datos.get("preguntas", [])

    # ---------- Etapa 2, Capa 2: analisis sustantivo (+ Nivel B) ----------

    def generar_preguntas_capa2(self, texto_sentencia, clasificacion, nucleo_narrativo):
        prompt = f"""Ya se ejecutaron la ETAPA 0 (clasificacion) y el Nivel A de la
ETAPA 1 (nucleo narrativo) para esta sentencia.

Clasificacion: {json.dumps(clasificacion, ensure_ascii=False)}
Nucleo narrativo: {nucleo_narrativo}

Ejecuta UNICAMENTE la CAPA 2 (analisis sustantivo) de la ETAPA 2, con su
bloque de Nivel B ("hechos relevantes para esta pregunta") para cada una.
Recuerda: si requiere_ponderacion es false, omite por completo la pregunta
de ponderacion (deja solo 4 preguntas en vez de 5).

Responde solo con este JSON:
{{
  "preguntas": [
    {{"hechos_relevantes": "..." | null, "texto": "..."}}
  ]
}}

<sentencia>
{texto_sentencia}
</sentencia>
"""
        datos = self._parsear_json(self._preguntar(prompt, max_tokens=7000))
        return datos.get("preguntas", [])

    # ---------- Etapa 4: contraste y diagnostico ----------

    def generar_diagnostico(self, texto_sentencia, preguntas_y_respuestas):
        """
        preguntas_y_respuestas: lista de dicts, uno por pregunta, en el mismo
        orden en que se presentaron al estudiante:
            [{"pregunta": "...", "hechos_relevantes": "...", "respuesta_estudiante": "..."}, ...]
        """
        prompt = f"""Ejecuta la ETAPA 4 (contraste y diagnostico). Estas son, en orden,
las preguntas formuladas y las respuestas que dio el estudiante:

<respuestas_estudiante>
{json.dumps(preguntas_y_respuestas, ensure_ascii=False, indent=2)}
</respuestas_estudiante>

Responde solo con un JSON de esta forma exacta (un elemento del arreglo por
cada pregunta recibida arriba, en el mismo orden):
{{
  "etapa": "diagnostico",
  "diagnostico": {{
    "elementos": [
      {{"elemento": "...", "respuesta_estudiante": "...", "veredicto": "...",
        "explicacion": "...", "fragmento_sentencia": "...", "puntos": 0.0}}
    ]
  }}
}}

<sentencia>
{texto_sentencia}
</sentencia>
"""
        datos = self._parsear_json(self._preguntar(prompt, max_tokens=8000))
        return self._extraer_seccion(datos, "diagnostico", campos_esperados=["elementos"])
