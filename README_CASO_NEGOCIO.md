# El caso de negocio, explicado con calma

Este documento explica, paso a paso y sin apurarse, la pregunta que responde el Módulo de Caso de Negocio (Sección 14 de `notebooks/07_drift_monitoreo.ipynb`): **¿vale la pena construir y mantener todo este sistema de monitoreo de drift, o es un gasto de ingeniería que no se justifica?** En el informe (`informe/informe.pdf`) esto aparece resumido en media página; acá va la versión larga, con el razonamiento completo y de dónde sale cada número.

## La pregunta, en cristiano

Imagina que eres el director de TI de un hospital y alguien te propone: "vamos a construir un sistema que vigile constantemente si el modelo de predicción de reingresos se está poniendo obsoleto, y que lo reentrene automáticamente cuando haga falta". Tu primera pregunta, razonablemente, es: **¿y eso cuánto cuesta, y cuánto me ahorra?** Si la respuesta es "cuesta más de lo que ahorra", no tiene sentido construirlo, por más elegante que sea el PSI o el disparador de reentrenamiento. Este módulo existe para responder esa pregunta con números, no con intuición.

## La comparación: dos maneras de operar el mismo modelo

Para que la comparación sea justa, no se inventa un escenario hipotético: se usa **la misma simulación de costos** que ya corre el sistema (la de la capa de decisión, Sección 10 del informe) y se le hace correr dos veces, bajo dos políticas distintas, sobre los mismos 7 bloques de prueba (pseudo-años 4 a 10 del dataset):

**Política A — "Desplegar y olvidar" (sin monitoreo).** Es lo que haría un equipo que entrena un modelo, lo pone en producción, calibra los umbrales de decisión una vez, y ya. No hay ni PSI, ni disparador de drift, ni reentrenamiento. El modelo que se entrenó con los datos de los primeros dos bloques sigue tomando decisiones cinco, ocho, diez bloques después, exactamente igual que el primer día.

**Política B — Con monitoreo (la que el sistema realmente recomienda).** Es la estrategia que el propio pipeline eligió como la mejor entre varias que probó (ventana deslizante de 3 bloques, reentrenada automáticamente conforme avanza el tiempo — ver `README_DATA_DRIFT.md` para el detalle de por qué se eligió esa y no otra). El "disparador" de este reentrenamiento es justamente el módulo de monitoreo de drift.

Para cada bloque de prueba, se calcula el costo esperado por cada 1,000 altas bajo cada política, usando la misma fórmula de costos que ya se usa en el resto del proyecto:

- Si el modelo marca a un paciente como **Alto Riesgo** y el paciente reingresa: cuesta la intervención ($C_i$) más el costo del reingreso descontado por la eficacia de la intervención.
- Si lo marca como Alto Riesgo y no reingresa: solo cuesta la intervención (falso positivo, pero barato).
- Si no lo marca y reingresa: cuesta el reingreso completo, sin descuento (falso negativo, el peor caso).

Esto no es un supuesto nuevo — es literalmente la función `costo_categorias()` que ya corre en la Sección 10, aplicada aquí a dos poblaciones de predicciones distintas (las del modelo estático vs. las del modelo con monitoreo).

## De dónde salen los números de costo (esto no nos lo inventamos)

| Parámetro | Valor | De dónde sale |
|---|---|---|
| $C_r$ — costo de un reingreso hospitalario | \$16,037 | Ghabowen et al. (2024), estimación de costo de reingresos evitables en pacientes diabéticos |
| $e$ — eficacia de la intervención de Alto Riesgo (reduce el riesgo relativo) | 0.18 (RR 0.82) | Leppin et al. (2014), metaanálisis de intervenciones para prevenir reingresos a 30 días; consistente con Drincic et al. (2017) |
| $C_i$ — costo de la intervención de Alto Riesgo (gestor de caso + conciliación farmacológica) | \$550 | Supuesto del equipo (no hay una cifra publicada específica para esta combinación exacta de intervenciones; se marca como tal en el propio código, igual que el resto de los parámetros de costo del proyecto) |
| $K$ — cupo máximo de pacientes marcados Alto Riesgo por bloque | 15% | Supuesto operativo, para evitar la "fatiga de alertas" documentada en van der Sijs et al. (2006) y Ancker et al. (2017) — si marcas a todo el mundo como urgente, el personal deja de hacerle caso a las alertas |

Es la misma matriz de costos que ya sustenta el análisis de curva de decisión (DCA) y la tabla de costos por política del resto del proyecto — no se inventó nada nuevo para este módulo, solo se reutilizó.

## Lo que realmente importa: no es el promedio, es la tendencia

Acá está la parte que, para mí, es el corazón de todo el caso de negocio. Si solo miras el promedio del ahorro a lo largo de los 7 bloques, ves una cifra modesta. Pero si miras bloque por bloque, la historia es otra:

| Bloque (pseudo-año de prueba) | Ahorro por cada 1,000 altas (con monitoreo vs. sin monitoreo) |
|---|---|
| 4 | \$924 |
| 5 | \$3,190 |
| 6 | \$3,662 |
| 7 | \$5,735 |
| 8 | \$12,854 |
| 9 | \$12,921 |
| 10 | \$15,114 |

El ahorro **se multiplica por más de 16 veces** entre el bloque 4 y el bloque 10. Esto no es casualidad ni ruido: es exactamente lo que uno esperaría si el "concept drift" es real. Un modelo que nunca se actualiza no falla de un día para el otro — va perdiendo precisión de a poco, a medida que la relación entre las variables clínicas y el riesgo de reingreso va cambiando (cambian las prácticas médicas, cambian los patrones de codificación de diagnósticos, cambia el uso de insulina, etc. — todo esto está documentado con evidencia en `README_DATA_DRIFT.md` y en la auditoría de PSI). Cuanto más tiempo pasa sin que nadie lo note, más caro sale seguir usando un modelo obsoleto para decidir a quién intervenir.

Dicho de otra forma: **el monitoreo de drift no es un gasto fijo que "más o menos" se paga solo — es una póliza de seguro cuyo valor crece exactamente en el escenario que más te importa evitar** (un modelo que lleva meses o años equivocándose cada vez más sin que nadie se dé cuenta).

## Pasando esto a una cifra anual (y siendo honestos sobre el supuesto)

El dataset no dice cuántas altas de pacientes diabéticos tiene un hospital por año — solo sabemos que en total hay unas 101,766 hospitalizaciones registradas a lo largo de 10 años en 130 hospitales de EE.UU. (esa es la fuente original del dataset: Strack et al., 2014). Eso da un promedio bajo por hospital individual, pero una red de hospitales mediana-grande fácilmente maneja volúmenes mayores. Para tener un número de referencia con el que trabajar, se usa un supuesto **explícitamente marcado como tal**, igual que se hace con $C_i$ y $K$: **50,000 altas de pacientes diabéticos al año**, del orden de una red hospitalaria mediana-grande. Si tu hospital o red tiene otro volumen, el cálculo es lineal — basta con multiplicar por tu propio número en vez de 50,000.

Con ese supuesto, promediando el ahorro por 1,000 altas de la tabla de arriba y multiplicando por 50 (porque 50,000 altas = 50 × 1,000):

- **Costo esperado sin monitoreo:** ≈ \$90,268,164 al año
- **Costo esperado con monitoreo:** ≈ \$89,879,592 al año
- **Ahorro bruto:** ≈ \$388,573 al año

(Nota: la cifra total de ~\$90 millones puede parecer enorme, pero es principalmente el costo *de los reingresos que van a pasar de todas formas* — la mayoría de los reingresos no son evitables ni con la mejor intervención del mundo, porque la eficacia $e$ es de solo 18%. El ahorro real que aporta el sistema no es esa cifra gigante, es la diferencia entre las dos políticas: los ~\$388 mil.)

## ¿Y cuánto cuesta mantener todo esto? (la parte que casi nadie calcula)

Acá es donde este caso de negocio intenta ser más honesto que el típico "el ROI es infinito porque el mantenimiento es gratis". Mantener un sistema de monitoreo de drift no es gratis: alguien tiene que revisar los reportes de PSI, alguien tiene que aprobar y ejecutar cada reentrenamiento, y todo eso corre en cómputo que cuesta dinero. Este argumento —que en un sistema de ML real el costo dominante no es entrenar el modelo una vez sino todo el trabajo de mantenimiento alrededor— es un punto bien conocido en la literatura de ingeniería de ML, viene del paper clásico de Sculley et al. (2015), *"Hidden Technical Debt in Machine Learning Systems"* (el que introdujo la imagen de que un modelo de ML es una cajita chiquita rodeada de un montón de "glue code" que es lo que realmente cuesta mantener).

Entonces el costo de mantenimiento se construyó de abajo hacia arriba, sumando piezas concretas (todas marcadas como supuestos razonables, no cifras mágicas):

**Actualización (20 de septiembre de 2026):** ya existe una estimación de costos de infraestructura AWS con tarifas públicas reales, publicada en [`despliegue/PROPUESTA_IMPLEMENTACION_SAGEMAKER.md`](despliegue/PROPUESTA_IMPLEMENTACION_SAGEMAKER.md) (Sección 9). De ahí sale el número de cómputo de la tabla de abajo, que reemplaza el placeholder genérico de \$60/mes que se usaba antes. Una aclaración importante: esa propuesta estima el costo **total** de operar el sistema en producción — endpoint de inferencia, ingesta SFTP, red privada (VPN/PrivateLink) y almacenamiento incluidos — en unos \$709–\$730 al mes (≈\$8,512–\$8,762 al año). La mayor parte de ese monto (endpoint, SFTP, red) es el costo de **servir el modelo en producción**, que se paga igual bajo la Política A (sin monitoreo) que bajo la Política B (con monitoreo): no es un costo atribuible a la decisión de monitorear, así que no entra en la tabla de abajo. Lo único que sí es atribuible al monitoreo es el cómputo de los jobs de SageMaker Processing/Training (el job batch de PSI/KS/calibración y los reentrenamientos), que es lo que se actualiza aquí, con el escenario más caro de los dos que ofrece la propuesta (90 h de instancia/mes, \$0.23/h) para no subestimar.

| Concepto | Supuesto | Costo anual estimado |
|---|---|---|
| Revisión mensual de PSI/KS/calibración por subgrupo | 3 horas/mes de un data scientist a \$70/hora | 3 × 70 × 12 = \$2,520 |
| Cómputo del monitoreo (job batch mensual, SageMaker Processing) | \$20.70/mes — 90 h de instancia × \$0.23/h, escenario de referencia de `despliegue/PROPUESTA_IMPLEMENTACION_SAGEMAKER.md` §9 | 20.70 × 12 ≈ \$248 |
| Reentrenamientos disparados por el módulo de drift | 16 horas de trabajo + \$40 de cómputo, por evento; en el horizonte evaluado se disparó 1 evento en 7 bloques pseudo-anuales | (16×70+40) × (1/7) ≈ \$166 |
| **Total** | | **≈ \$2,934 al año** |

## El resultado final

| | |
|---|---|
| Ahorro bruto anual (con 50,000 altas/año) | \$388,573 |
| Costo de mantenimiento anual | \$2,934 |
| **Beneficio neto anual** | **\$385,639** |
| **Retorno sobre la inversión (ROI)** | **≈132 veces** |

O sea: por cada dólar que cuesta mantener el sistema de monitoreo, se ahorran del orden de 132 dólares en costos de reingreso mal gestionados. Incluso si tus supuestos de costo de mantenimiento están subestimados por un factor de 10, el sistema seguiría siendo largamente rentable.

## Lo que este número NO incluye (para no venderlo de más)

Siendo honestos, hay valor que se dejó fuera del cálculo a propósito, para no inflar la cifra:

- **La penalización del HRRP.** El *Hospital Readmissions Reduction Program* de EE.UU. penaliza económicamente a los hospitales con exceso de reingresos en ciertas condiciones. La diabetes no es una de las condiciones objetivo directas del programa, pero es una comorbilidad tan frecuente en esas poblaciones que reducir reingresos diabéticos probablemente ayuda a bajar también esas penalizaciones — pero como no hay una cifra confiable y específica para este proyecto, no se metió al cálculo. Es upside adicional, no contado.
- **El costo de NO tener el sistema y enterarse tarde.** El cálculo compara "con monitoreo" vs. "sin monitoreo pero con el mismo modelo bien entrenado al inicio". No modela el escenario todavía peor de un modelo que nadie audita nunca y que, sin que nadie lo note, empieza a discriminar sistemáticamente en contra de algún grupo de pacientes (ver la sección de equidad en `README_DATA_DRIFT.md` — ese es un riesgo real, y detectarlo a tiempo también vale dinero y reputación, pero es mucho más difícil de cuantificar en dólares).

## Cómo reproducir este número tú misma

Todo el cálculo está en la Sección 14 de `notebooks/07_drift_monitoreo.ipynb` (celda de "Caso de negocio"), y usa exactamente las mismas funciones (`costo_categorias`, `umbrales`, `ModeloCalibrado`) que ya corren en el resto del notebook — no hay ningún cálculo paralelo ni inventado aparte. Los resultados numéricos quedan guardados en:

- `resultados/caso_negocio_por_bloque.csv` — la tabla de ahorro bloque por bloque.
- `resultados/caso_negocio_resumen.csv` — el resumen anualizado (los números de este documento).
- `resultados/fig_caso_negocio.png` — el gráfico de barras que compara las cuatro cifras (sin monitoreo, con monitoreo, mantenimiento, beneficio neto).
- `despliegue/PROPUESTA_IMPLEMENTACION_SAGEMAKER.md` (Sección 9) — de donde sale el costo de cómputo del monitoreo usado en la tabla de mantenimiento, con la estimación completa de infraestructura AWS de producción.

Si quieres probar con tu propio volumen de altas anuales, basta con cambiar `ALTAS_ANUALES` al inicio de esa celda y volver a correrla — todo lo demás se recalcula solo.

## Fuentes citadas en este documento

- Ghabowen, I., et al. (2024). Costo de reingresos hospitalarios atribuibles a diabetes.
- Leppin, A. L., et al. (2014). Preventing 30-day hospital readmissions: a systematic review and meta-analysis of randomized trials. *JAMA Internal Medicine*, 174(7), 1095–1107.
- Drincic, A., Pfeffer, E., Luo, J., & Goldner, W. S. (2017). The effect of diabetes case management and Diabetes Resource Nurse program on readmissions of patients with diabetes mellitus. *Journal of Clinical & Translational Endocrinology*, 8, 29–34.
- van der Sijs, H., et al. (2006). Overriding of drug safety alerts in computerized physician order entry. *JAMIA*, 13(2), 138–147.
- Ancker, J. S., et al. (2017). Effects of workload, work complexity, and repeated alerts on alert fatigue in a clinical decision support system. *BMC Medical Informatics and Decision Making*, 17(1).
- Strack, B., et al. (2014). Impact of HbA1c measurement on hospital readmission rates: analysis of 70,000 clinical database patient records. *BioMed Research International*, 2014.
- Sculley, D., et al. (2015). Hidden technical debt in machine learning systems. *NeurIPS* 28.
- van Walraven, C., et al. (2011). Proportion of hospital readmissions deemed avoidable: a systematic review. *CMAJ*, 183(7), E391–E402. (Contexto del HRRP mencionado arriba)
