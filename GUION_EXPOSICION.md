# Guion de exposición — Sistema Inteligente Adaptativo para Reingreso Hospitalario

> Guion tipo pitch para la exposición oral (~10 min). No reemplaza al informe ni a la infografía — es material de apoyo para hablar, con gancho en vez de lectura de rúbrica.

## Corrección de dato

El dataset tiene **11.2% de prevalencia de reingreso** (no 21%). Usa esa cifra si alguien pregunta — es la que respalda todo lo demás.

---

## Guion

### 00:00–00:50 — Gancho

Reingresar a un paciente al hospital cuesta en promedio **16 mil dólares**. Y en pacientes diabéticos, según nuestros datos, **1 de cada 9** vuelve a ser hospitalizado antes de cumplir 30 días desde su alta.

La diabetes en sí no tiene una multa directa del gobierno — pero casi siempre viene acompañada de otras condiciones que sí la tienen: insuficiencia cardiaca, infarto, neumonía. Entonces el hospital paga dos veces: paga el reingreso, y encima puede perder plata por la penalidad.

Y lo que más nos sorprendió investigando esto: hasta un **27% de esos reingresos se consideran evitables**. No es mala suerte, es un problema de proceso — cómo se concilian los medicamentos, qué tan claras son las indicaciones al salir, si alguien hace seguimiento después.

El hospital ya sabe cómo prevenir esto: llamar al paciente, revisar su medicación, agendarle una cita temprana. El problema es que no puede hacerle eso a **todos**. No hay personal para eso. Entonces la pregunta real no es "¿cómo evitamos reingresos?" — ya se sabe cómo. La pregunta es **¿a quién se lo hacemos primero?**

Por eso propusimos un sistema de IA.

### 00:50–01:40 — Qué queremos lograr

La idea es simple: antes de que un paciente diabético reciba el alta, el sistema calcula qué tan probable es que vuelva en menos de 30 días, y se lo muestra al médico como un semáforo — Bajo, Moderado, Alto — junto con los factores que más pesaron en esa predicción.

Lo que buscamos a gran escala es eso: un sistema que prediga ese riesgo, que **siga siendo confiable con el paso del tiempo** — porque la medicina cambia, los tratamientos cambian — y que apoye la decisión médica sin reemplazarla. El sistema recomienda, el médico decide. Siempre.

Para llegar ahí tuvimos que resolver varias cosas en el camino: entender bien el historial clínico y dejarlo listo para un modelo, comparar distintos modelos de clasificación hasta encontrar el más confiable, diseñar cómo ese riesgo se convierte en una decisión real con costos de por medio, pensar cómo se llevaría esto a producción en la nube, y construir la pieza que lo hace *adaptativo* — un monitoreo que sepa detectar cuándo el modelo ya no está funcionando bien.

### 01:40–02:30 — Cómo funciona por dentro

Imagínense el flujo completo: el paciente está por salir de alta, el sistema jala sus datos de la historia clínica, un modelo calcula su riesgo, otro módulo revisa qué tan seguro está de esa predicción, y con eso se arma la clasificación — Bajo, Moderado, Alto. Según el nivel, se sugiere una acción: desde nada, hasta una llamada de control, hasta una cita presencial prioritaria.

Y en paralelo, corriendo todo el tiempo por detrás, hay un módulo que vigila si el modelo se está quedando viejo. Si detecta que sí, dispara un reentrenamiento. Esa es la pieza que hace que esto no sea "un modelo más" — es un sistema que se cuida solo, pero nunca decide solo.

### 02:30–03:10 — Límites y cómo sabemos si funciona

Pusimos límites claros desde el día uno. El sistema nunca decide solo — no cambia recetas ni da altas. Los datos de salud están protegidos por ley, así que todo tiene que ser auditable. Y como los datos son de hospitales de EE. UU., no podemos prometer que esto funcione igual en Perú sin recalibrar con datos locales.

Y no nos conformamos con medir "qué tan bueno es el modelo prediciendo". Lo medimos en tres planos: si distingue bien a los pacientes de riesgo, si usarlo de verdad ahorra plata comparado con no hacer nada, y si es justo — que no deje sistemáticamente desatendido a un grupo de pacientes por su edad o su raza.

### 03:10–03:50 — Los datos

Trabajamos con más de 100 mil hospitalizaciones reales, de 130 hospitales de Estados Unidos, entre 1999 y 2008. El dataset no trae fecha exacta, así que ordenamos los registros por el número de cada hospitalización y armamos 10 bloques, como si fueran 10 años de operación.

Y antes de entrenar nada, hicimos algo que casi nadie hace: 13 pruebas para comprobar que el modelo no estuviera "haciendo trampa" — viendo información que en la realidad no tendría disponible todavía. Encontramos dos errores así y los corregimos. Si no lo hubiéramos hecho, todos los números que van a ver después serían mentira.

### 03:50–04:40 — Los modelos

Probamos tres: ElasticNet, que es el más simple; Random Forest, un conjunto de árboles; y XGBoost, más sofisticado, pensado para capturar relaciones complejas entre diagnósticos y medicación.

Ganó Random Forest — por poco, pero ganó — con un ROC-AUC de 0.664. Y aquí un dato importante: en este tipo de problema, con datos de historia clínica, la literatura dice que rara vez se supera 0.70. O sea, no es que nuestro modelo sea mediocre — es que este problema, con estos datos, tiene un techo. Y lo sabíamos desde antes de entrenar, no lo estamos justificando después.

### 04:40–05:30 — Cómo se usaría en la vida real

Diseñamos el camino completo hacia producción: la historia clínica manda los datos, pasan por una API privada, el modelo responde en menos de un segundo, y el médico ve el resultado en pantalla — la probabilidad, qué tan seguro está el modelo, y por qué.

Y el modelo **nunca actúa solo**. Solo predice. La decisión y la acción son del profesional de salud. Por detrás, un proceso separado revisa si el modelo necesita actualizarse, y si es así, una persona tiene que aprobar el reemplazo antes de que entre en uso — nunca se actualiza solo sin que alguien lo revise.

### 05:30–07:00 — El corazón del proyecto: el modelo se envejece

Esta es la parte que nos diferencia. Un modelo entrenado hoy, con los medicamentos y protocolos de hoy, puede empezar a fallar en cinco años sin avisar — porque el mundo cambió y el modelo no.

Simulamos 10 años de operación y probamos cuatro formas de manejar eso: nunca tocar el modelo; reentrenarlo cada año con todo el historial acumulado; reentrenarlo cada año pero solo con los últimos tres años, botando lo viejo a propósito; o esperar a que salte una alerta.

¿Qué pasa si nunca lo tocas? Se degrada. No de golpe — de a poco, casi sin que te des cuenta, que es lo peligroso. ¿Y cuál ganó? La ventana de **tres años**: la que "olvida" a propósito lo más antiguo. Y complementamos eso con un semáforo que vigila si las variables clínicas — uso de insulina, número de diagnósticos — se ven distintas a como empezaron. Verde, amarillo, rojo.

### 07:00–08:20 — El número que importa: la plata

Y acá viene la pregunta que de verdad le importa a un hospital: ¿esto vale la plata que cuesta construirlo?

El sistema no interviene a todos. Solo al 15% de mayor riesgo por periodo. Esa llamada de seguimiento cuesta 550 dólares. Un reingreso cuesta 16 mil. Con esos dos números solos ya se entiende por qué conviene ser selectivo.

En el escenario normal, usar el modelo ahorra **25 mil dólares por cada mil altas**, comparado con no hacer nada. Si el hospital está saturado y cada reingreso sale más caro, el ahorro sube a 53 mil. Solo en un escenario extremo — donde la intervención funciona muchísimo mejor de lo esperado — casi da lo mismo llamar a todos que usar el modelo, y el modelo pierde por un margen chico. Lo dejamos así, sin esconderlo.

Llevado a un hospital mediano, el sistema se paga solo en el primer año. Llevado a una red de hospitales, como la que originó estos datos, se paga en **17 días**. Y lo más importante: ese ahorro **crece con el tiempo** si el modelo se mantiene actualizado — que es exactamente lo que hace el módulo de monitoreo que acabamos de explicar. No es casualidad, es la misma historia contada en plata.

### 08:20–09:10 — ¿Es justo? ¿Se puede confiar?

Antes de cerrar, revisamos algo que a veces se ignora: si el modelo trata igual a todos los grupos de pacientes. Comparamos por edad y por raza, y en la mayoría de los casos el modelo se mantiene dentro de lo esperado. También mostramos qué factores pesan más en cada predicción — insulina, diagnósticos, procedimientos — para que el médico pueda confiar o cuestionar el resultado. Y responde en 80 milisegundos, muy por debajo del límite que nos pusimos.

De los seis criterios de éxito que definimos desde el inicio, cumplimos cinco. El único que no, es justamente ese escenario extremo del caso de negocio que ya mencionamos — y preferimos mostrarlo tal cual, en vez de maquillarlo.

### 09:10–09:45 — Cierre

Entonces, no construimos solo un modelo que predice reingresos. Construimos un sistema que predice, decide cuánto confiar en esa predicción, sugiere una acción, y **sabe cuándo dejar de confiar en sí mismo** y pedir que lo actualicen.

Esa es la apuesta del proyecto: no basta con predecir bien hoy. Hay que seguir siendo confiable mañana, y el próximo año, y el que sigue.

---

## Preguntas típicas (respuesta corta, mismo tono)

**¿Por qué no usaron la fecha real de alta?**
El dataset público no trae fecha real, así que usamos el número de cada hospitalización como un proxy del orden — y no lo asumimos a ciegas: lo comprobamos. Para el mismo paciente, el encuentro siguiente casi siempre "recuerda" el anterior, en el 85% de los casos. Si el orden fuera al azar, eso no pasaría.

**¿Por qué Random Forest y no XGBoost, si XGBoost suele ser mejor?**
Porque en este dataset, con esta preparación, Random Forest sacó mejor ROC-AUC y PR-AUC que XGBoost en la comparación inicial. XGBoost es más potente en teoría, pero con datos tabulares de este tamaño la ventaja no siempre se nota — y acá no se notó.

**¿Qué pasa si el modelo se equivoca y no marca a alguien que sí iba a reingresar?**
Se le puede escapar un paciente — un falso negativo. Por eso nunca dejamos que el sistema actúe solo: el médico ve más información que la que tiene el modelo, y la decisión final siempre es de él.

**¿Por qué no está en producción todavía?**
Porque encontramos algo que no nos cuadraba: la selección de pacientes de alto riesgo no es igual de pareja entre todos los grupos. Preferimos frenar ahí, documentarlo como bloqueante, y no lanzar algo que podría ser injusto con un grupo de pacientes.

**¿Por qué eligieron la ventana de 3 años y no otra estrategia?**
Porque fue la que dio mejor equilibrio entre precisión y estabilidad de las cuatro que probamos. "Solo con alerta" es más barata en cómputo, pero en el periodo que evaluamos solo se activó una vez — no es suficiente evidencia todavía para confiar en ella en producción.

**¿De dónde salen los $16,037 y los $550?**
El costo de reingreso viene de un estudio de 2024 sobre costos hospitalarios atribuibles a diabetes. El costo de intervención es una estimación propia del equipo, declarada explícitamente como supuesto — no la escondimos como si fuera un dato medido.

---

## Números clave para tener a mano

| Dato | Valor |
|---|---|
| Costo de un reingreso | $16,037 |
| Costo de intervenir a un paciente | $550 |
| Reducción de riesgo por intervención | 18% |
| Prevalencia de reingreso en el dataset | 11.2% |
| Reingresos evitables (literatura) | 27.1% (mediana) |
| Tope de pacientes en Alto Riesgo | 15% por periodo |
| ROC-AUC modelo principal (Random Forest) | 0.664 |
| Mejor estrategia de adaptación | Ventana deslizante de 3 años (ROC-AUC 0.680) |
| Ahorro caso base | $25,008 / 1,000 altas |
| Ahorro alta ocupación | $53,357 / 1,000 altas |
| Escenario donde el modelo pierde | Optimista (e=0.38): −$8,829 / 1,000 altas |
| Payback, hospital mediano | ~1 año (beneficio neto $18,000) |
| Payback, red de ~17 hospitales | ~17 días (beneficio neto $1.19M) |
| Latencia p95 | 79.5 ms (límite: 2,000 ms) |
| Criterios de éxito cumplidos | 5 de 6 |
