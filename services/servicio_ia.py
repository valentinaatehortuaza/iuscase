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

Identifica ademas `derechos_vulnerados`: una lista de 1 a 3 derechos
fundamentales en juego en la sentencia (los que efectivamente se alegan o
resuelven, no los que solo se mencionan de pasada), tomados UNICAMENTE de
este catalogo fijo -- nunca inventes un valor fuera de esta lista, y si
ninguno encaja bien usa "otro":
"salud" | "debido_proceso" | "minimo_vital" | "vida_dignidad" |
"seguridad_social" | "igualdad" | "vivienda_digna" | "educacion" | "otro"
Ordena la lista del derecho mas central al caso al menos central.

Salida de esta etapa (JSON):
{
  "tipo_tutela": "particular" | "autoridad_publica" | "providencia_judicial",
  "fundamento_particular": "servicio_publico" | "interes_colectivo" |
                            "subordinacion_indefension" | null,
  "requiere_ponderacion": true | false,
  "legitimacion_activa_especial": "agencia_oficiosa" | "representacion_menor" |
                                    "ninguna" | "otra: <descripcion>",
  "derechos_vulnerados": ["salud", "minimo_vital"]
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

Ademas del diagnostico por elemento, evalua UNA SOLA VEZ, de forma holistica
sobre el conjunto de las respuestas, la `calidad_sustento`: no si el
contenido juridico es correcto (eso ya lo mide el veredicto de cada
elemento), sino COMO esta argumentado -- si las respuestas citan fundamento
normativo o jurisprudencial concreto (no solo afirman sin sustento), si la
redaccion es clara y esta bien estructurada, y si usa terminologia juridica
precisa. Produce:
- `nivel`: "alta" | "media" | "baja".
- `justificacion`: 1-2 frases explicando por que, en terminos concretos
  (ejemplo: "cita la norma aplicable en la mayoria de respuestas pero la
  redaccion es desordenada en dos de ellas").

-------------------------------------------------------------------------------
FORMATO DE SALIDA (JSON, sin texto adicional antes o despues)
-------------------------------------------------------------------------------
Responde EXCLUSIVAMENTE con un objeto JSON valido, sin texto antes ni despues,
y solo con los campos correspondientes a la etapa que se te pida ejecutar en
el mensaje del usuario.
""".strip()

# Se envia como lista de UN bloque (en vez de un string plano) para poder
# marcarlo con cache_control: este prompt de sistema es EXACTAMENTE el mismo
# en todas las llamadas de toda la app (siempre), asi que Anthropic lo cachea
# del lado del servidor y en cada llamada posterior lo cobra a ~10% de su
# precio normal en vez de completo. TTL de 1 hora (en vez del default de 5
# minutos) para que siga sirviendo del cache aunque pasen varios minutos
# entre una llamada y la siguiente (p. ej. mientras el estudiante responde
# las preguntas antes de pedir el diagnostico).
SYSTEM_PROMPT_CACHEADO = [
    {
        "type": "text",
        "text": SYSTEM_PROMPT,
        "cache_control": {"type": "ephemeral", "ttl": "1h"},
    }
]


# Tope de seguridad para los reintentos automaticos de _preguntar cuando la
# respuesta de la IA se corta por max_tokens (ver _preguntar). Muy por debajo
# del maximo real de salida del modelo (128,000 tokens aprox.) -- si se
# llegara hasta aca es una señal de que algo esta genuinamente fuera de lo
# normal, no un simple ajuste fino de limite.
LIMITE_MAXIMO_TOKENS_SALIDA = 32000


class ServicioIA:
    """
    Orquesta el flujo de estudio de casos de IUSCase usando la API de
    Anthropic (Claude), siguiendo el prompt de sistema consolidado (arriba).

    El flujo hace 5 llamadas a la IA por caso (etapas 0, 1, 2 -partida en dos
    capas-, y 4 del prompt; la etapa 3 no genera contenido, solo espera las
    respuestas del estudiante):
      1. clasificar_sentencia()       -> Etapa 0
      2. generar_nucleo_narrativo()   -> Etapa 1 (Nivel A)
      3. generar_preguntas_capa1()    -> Etapa 2, Capa 1 (+ Nivel B)
      4. generar_preguntas_capa2()    -> Etapa 2, Capa 2 (+ Nivel B)
      5. generar_diagnostico()        -> Etapa 4

    Las primeras 4 llamadas se hacen juntas, en una sola peticion, al subir
    la sentencia; la quinta se hace despues, cuando el estudiante envia sus
    respuestas. Las 5 llamadas reenvian el MISMO texto de la sentencia -- por
    eso ese texto se pasa como bloque cacheado (ver _preguntar): Anthropic lo
    cobra completo solo la primera vez y a ~10% del precio en las siguientes
    4, mientras sigan dentro de la ventana de 1 hora del cache.

    Requiere la variable de entorno ANTHROPIC_API_KEY. Crea un archivo .env
    en la raiz del proyecto (no lo subas a git) con:
        ANTHROPIC_API_KEY=tu_clave_aqui
    """

    def __init__(self):
        self._cliente = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        # Acumula los tokens de entrada/salida de las llamadas a la API para
        # poder calcular el costo real por caso. Se reinicia con
        # obtener_y_reiniciar_uso() despues de cada tramo del flujo.
        #
        # Con prompt caching, Anthropic reporta el input de cada llamada en
        # 3 campos separados en vez de uno solo (usage.input_tokens): lo que
        # se escribio al cache por primera vez (cache_creation_input_tokens),
        # lo que se leyo del cache ya existente (cache_read_input_tokens, a
        # ~10% del precio normal) y lo que se proceso normal, sin cache
        # (input_tokens). Para no romper lo que ya depende de
        # tokens_entrada (el conteo historico por caso en la base de datos),
        # se sigue acumulando como un solo numero = la suma de los 3 campos
        # (volumen total de tokens de entrada procesados, cacheados o no).
        # El ahorro real en USD por el cache se puede ver en el dashboard de
        # uso de la consola de Anthropic, que si desglosa cache read/write.
        self._tokens_entrada_acumulados = 0
        self._tokens_salida_acumulados = 0

    # ---------- utilidades internas ----------

    def _preguntar(self, prompt, max_tokens=1500, texto_cacheable=None):
        """
        texto_cacheable: si se pasa (el texto de la sentencia, ya envuelto
        en <sentencia>...</sentencia>), se envia como un bloque de contenido
        APARTE, SIEMPRE PRIMERO en el mensaje, y marcado con cache_control.
        Las llamadas de un mismo caso reenvian este mismo texto una y otra
        vez (ver docstring de ServicioIA): al ser un bloque identico, byte
        por byte, y en la misma posicion en cada llamada, Anthropic lo
        reconoce como ya procesado desde la segunda llamada en adelante y lo
        cobra a ~10% de su precio normal en vez de completo.
        """
        if texto_cacheable:
            contenido = [
                {
                    "type": "text",
                    "text": texto_cacheable,
                    "cache_control": {"type": "ephemeral", "ttl": "1h"},
                },
                {"type": "text", "text": prompt},
            ]
        else:
            contenido = prompt

        respuesta = self._cliente.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT_CACHEADO,
            messages=[{"role": "user", "content": contenido}],
        )
        uso = respuesta.usage
        self._tokens_entrada_acumulados += (
            uso.input_tokens
            + (getattr(uso, "cache_creation_input_tokens", 0) or 0)
            + (getattr(uso, "cache_read_input_tokens", 0) or 0)
        )
        self._tokens_salida_acumulados += uso.output_tokens
        if respuesta.stop_reason == "max_tokens":
            if max_tokens < LIMITE_MAXIMO_TOKENS_SALIDA:
                # No alcanzo a terminar con este limite -- en vez de fallarle
                # al estudiante, reintentamos solos con el doble de espacio
                # (hasta un tope de seguridad). Asi la misma app funciona
                # bien con sentencias cortas y simples (limites bajos de
                # partida = mas rapido y mas barato) y con sentencias largas
                # o inusualmente complejas (sube el limite automaticamente
                # solo cuando de verdad hace falta, sin que el estudiante
                # tenga que volver a intentarlo ni perder su avance).
                nuevo_limite = min(max_tokens * 2, LIMITE_MAXIMO_TOKENS_SALIDA)
                return self._preguntar(
                    prompt, max_tokens=nuevo_limite, texto_cacheable=texto_cacheable
                )
            raise ValueError(
                "La respuesta de la IA se corto incluso con el tope de seguridad "
                f"de max_tokens={max_tokens} para este paso. Esto es muy inusual "
                "-- puede ser una sentencia extremadamente larga o compleja. "
                "Intenta con otra sentencia o avisa para revisar el caso."
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

    def obtener_y_reiniciar_uso(self):
        """
        Devuelve (tokens_entrada, tokens_salida) acumulados desde la ultima
        vez que se llamo este metodo (o desde que se creo el objeto), y
        reinicia el contador a cero. Se usa para guardar el costo real de
        cada caso en la base de datos.
        """
        tokens = (self._tokens_entrada_acumulados, self._tokens_salida_acumulados)
        self._tokens_entrada_acumulados = 0
        self._tokens_salida_acumulados = 0
        return tokens

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

    # ---------- Etapa -1: validacion de entrada (antes de gastar las 4 llamadas caras) ----------

    def validar_es_sentencia_tutela(self, texto_sentencia):
        """
        Chequeo rapido y barato (max_tokens bajo) para detectar ANTES de las
        llamadas caras si lo que se subio ni siquiera es una sentencia de
        revision de tutela de la Corte Constitucional de Colombia (por
        ejemplo: un PDF de otra cosa, un contrato, o una sentencia real pero
        de otro tribunal). Si pasa este chequeo, el texto queda cacheado y
        las llamadas siguientes (clasificar_sentencia y las demas) lo leen
        del cache en vez de pagar por reprocesarlo.
        """
        instrucciones = """Antes de cualquier otra cosa, tu UNICA tarea aqui es verificar si el
texto en <sentencia> es el texto (completo o un extracto sustancial) de una
SENTENCIA DE REVISION DE TUTELA emitida por la Corte Constitucional de
Colombia -- normalmente identificable por un encabezado como "CORTE
CONSTITUCIONAL" y una numeracion tipo T-### o SU-### de un año dado.

NO es una sentencia de tutela de la Corte Constitucional si, por ejemplo,
es: un documento de otro tipo (contrato, articulo, ley, concepto), una
sentencia de otro tribunal (Consejo de Estado, Corte Suprema de Justicia,
un juzgado o tribunal de instancia), o un texto sin relacion con una
decision judicial de tutela.

Responde SOLO con este JSON, sin nada mas (usa true o false, no texto):
{"es_sentencia_tutela": true o false, "motivo": "si es false: una frase breve en español explicando por que no califico, pensada para mostrarsela directamente al estudiante. Si es true: cadena vacia."}
"""
        sentencia_bloque = f"<sentencia>\n{texto_sentencia}\n</sentencia>"
        datos = self._parsear_json(
            self._preguntar(instrucciones, max_tokens=300, texto_cacheable=sentencia_bloque)
        )
        return {
            "es_sentencia_tutela": bool(datos.get("es_sentencia_tutela")),
            "motivo": datos.get("motivo") or "",
        }

    # ---------- Etapa 0: clasificacion ----------

    def clasificar_sentencia(self, texto_sentencia):
        instrucciones = """Arriba tienes el texto completo de la sentencia. Ejecuta UNICAMENTE
la ETAPA 0 (clasificacion) para esa sentencia. Responde solo con el JSON de
esa etapa:

{"etapa": "clasificacion", "clasificacion": {...}}
"""
        sentencia_bloque = f"<sentencia>\n{texto_sentencia}\n</sentencia>"
        datos = self._parsear_json(
            self._preguntar(instrucciones, max_tokens=4000, texto_cacheable=sentencia_bloque)
        )
        return self._extraer_seccion(
            datos, "clasificacion",
            campos_esperados=["tipo_tutela", "requiere_ponderacion", "fundamento_particular"],
        )

    # ---------- Etapa 1 (Nivel A): nucleo narrativo ----------

    def generar_nucleo_narrativo(self, texto_sentencia, clasificacion):
        instrucciones = f"""Arriba tienes el texto completo de la sentencia. Ya se ejecuto la
ETAPA 0 para esa sentencia, con este resultado:
{json.dumps(clasificacion, ensure_ascii=False)}

Ejecuta UNICAMENTE el NIVEL A de la ETAPA 1 (nucleo narrativo): quienes son
las partes, que relacion tuvieron, que ocurrio a nivel procesal (quien
demando a quien, que decidio la instancia previa si aplica, por que se acude
a tutela) y el problema juridico. NO generes todavia preguntas ni bloques de
Nivel B.

Responde solo con este JSON:
{{"nucleo_narrativo": "...", "problema_juridico": "..."}}
"""
        sentencia_bloque = f"<sentencia>\n{texto_sentencia}\n</sentencia>"
        datos = self._parsear_json(
            self._preguntar(instrucciones, max_tokens=6000, texto_cacheable=sentencia_bloque)
        )
        return self._extraer_seccion(
            datos, "exposicion",
            campos_esperados=["nucleo_narrativo", "problema_juridico"],
        )

    # ---------- Etapa 2, Capa 1: filtro procesal (+ Nivel B) ----------

    def generar_preguntas_capa1(self, texto_sentencia, clasificacion, nucleo_narrativo):
        instrucciones = f"""Arriba tienes el texto completo de la sentencia. Ya se ejecutaron la
ETAPA 0 (clasificacion) y el Nivel A de la ETAPA 1 (nucleo narrativo) para
esa sentencia.

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
"""
        sentencia_bloque = f"<sentencia>\n{texto_sentencia}\n</sentencia>"
        datos = self._parsear_json(
            self._preguntar(instrucciones, max_tokens=10000, texto_cacheable=sentencia_bloque)
        )
        return datos.get("preguntas", [])

    # ---------- Etapa 2, Capa 2: analisis sustantivo (+ Nivel B) ----------

    def generar_preguntas_capa2(self, texto_sentencia, clasificacion, nucleo_narrativo):
        instrucciones = f"""Arriba tienes el texto completo de la sentencia. Ya se ejecutaron la
ETAPA 0 (clasificacion) y el Nivel A de la ETAPA 1 (nucleo narrativo) para
esa sentencia.

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
"""
        sentencia_bloque = f"<sentencia>\n{texto_sentencia}\n</sentencia>"
        datos = self._parsear_json(
            self._preguntar(instrucciones, max_tokens=11000, texto_cacheable=sentencia_bloque)
        )
        return datos.get("preguntas", [])

    # ---------- Etapa 4: contraste y diagnostico ----------

    def generar_diagnostico(self, texto_sentencia, preguntas_y_respuestas):
        """
        preguntas_y_respuestas: lista de dicts, uno por pregunta, en el mismo
        orden en que se presentaron al estudiante:
            [{"pregunta": "...", "hechos_relevantes": "...", "respuesta_estudiante": "..."}, ...]
        """
        instrucciones = f"""Arriba tienes el texto completo de la sentencia. Ejecuta la ETAPA 4
(contraste y diagnostico). Estas son, en orden, las preguntas formuladas y
las respuestas que dio el estudiante:

<respuestas_estudiante>
{json.dumps(preguntas_y_respuestas, ensure_ascii=False, indent=2)}
</respuestas_estudiante>

Responde solo con un JSON de esta forma exacta (un elemento del arreglo por
cada pregunta recibida arriba, en el mismo orden, mas el bloque
"calidad_sustento" UNA SOLA VEZ para todo el caso):
{{
  "etapa": "diagnostico",
  "diagnostico": {{
    "elementos": [
      {{"elemento": "...", "respuesta_estudiante": "...", "veredicto": "...",
        "explicacion": "...", "fragmento_sentencia": "...", "puntos": 0.0}}
    ],
    "calidad_sustento": {{"nivel": "alta", "justificacion": "..."}}
  }}
}}
"""
        sentencia_bloque = f"<sentencia>\n{texto_sentencia}\n</sentencia>"
        datos = self._parsear_json(
            self._preguntar(instrucciones, max_tokens=20000, texto_cacheable=sentencia_bloque)
        )
        return self._extraer_seccion(datos, "diagnostico", campos_esperados=["elementos"])
