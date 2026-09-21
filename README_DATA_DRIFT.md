# Data Drift & Concept Drift — documentación completa

Este documento detalla el módulo de monitoreo y adaptación ante drift del sistema de predicción de reingreso hospitalario: qué se mide, cómo, con qué resultados, y qué limitaciones tiene. Es la referencia técnica de la Sección 8-10 de `informe/informe.tex`. Vive principalmente en `notebooks/07_drift_monitoreo.ipynb` (Secciones 7-14), construido sobre el modelo elegido en `notebooks/04_modelado.ipynb` (Fase 3).

## 1. Marco conceptual

Se sigue la definición estándar de la literatura (y de la clase de Concept Drift del curso): un **concepto** es la distribución conjunta $P(X, y)$; existe **drift** entre dos instantes si $P_{t_0}(X, y) \neq P_{t_1}(X, y)$.

- **Drift real:** cambia $P(y \mid X)$ — la relación entre las variables y la etiqueta cambia. Exige reentrenar: el patrón que el modelo aprendió ya no es válido.
- **Drift virtual (covariate shift):** cambia $P(X)$ pero no $P(y \mid X)$. Puede degradar la calibración sin necesariamente degradar la discriminación.

En este proyecto:
- El **Mapeo de degradación (E1)** mide drift real (el modelo no se actualiza; si su desempeño cae, es porque la relación X→y cambió respecto a lo aprendido).
- El **monitoreo de PSI/KS por variable** mide drift virtual / covariate shift (cambia la distribución de entrada, independientemente de si eso afecta a la predicción).

## 2. Por qué ventanas fijas (y no un stream real)

El dataset no tiene fecha de admisión explícita. `encounter_id` se usa como proxy cronológico, validado en `notebooks/03_preprocesamiento.ipynb` (el siguiente encuentro del mismo paciente registra hospitalizaciones previas en 84.9% de los casos vs. 47.4% en orden inverso — si el orden fuera arbitrario, esa asimetría no existiría). Sobre ese eje se arman **10 bloques pseudo-temporales** de tamaño equivalente (`bloque = period // 2 + 1`), simulando 10 periodos anuales. Todo el monitoreo de drift compara bloques entre sí, nunca registros individuales.

## 3. Monitoreo de distribución de features (data drift básico) — Sección 7

**Qué hace:** para cada bloque $b > 1$, compara su distribución contra el **bloque de referencia fijo B1** en un conjunto de variables clínicas clave:
- Numéricas: `time_in_hospital`, `num_lab_procedures`, `num_procedures`, `num_medications`, `number_outpatient`, `number_emergency`, `number_inpatient`, `number_diagnoses_capped`.
- Categóricas: `insulin`, `metformin`, `rosiglitazone`, `pioglitazone`, `A1Cresult`, `change`, `diabetesMed`, `admission_type_grp`, y `race` (esta última **solo para trazabilidad de equidad**, no es feature del modelo).

**Cómo:**
1. **PSI (Population Stability Index)** — para numéricas, se cortan los cuantiles de B1 en 10 bins y se compara la proporción de cada bin en B1 vs. el bloque actual; para categóricas, se compara la proporción de cada categoría. Fórmula: $PSI = \sum (q_i - p_i) \ln(q_i / p_i)$. Umbrales estándar de industria: `<0.10` estable, `0.10–0.25` vigilar, `>0.25` alerta.
2. **Prueba de hipótesis complementaria** — Kolmogorov-Smirnov para numéricas, $\chi^2$ de independencia para categóricas, con **corrección de Bonferroni** por comparaciones múltiples ($\alpha = 0.01 / n_{tests}$, con $n_{tests} = 17 \text{ variables} \times 9 \text{ bloques} = 153$).

**Por qué PSI + prueba de hipótesis y no solo una:** PSI es una medida de *tamaño de efecto* (cuánto cambió la distribución) pero no da significancia estadística; la prueba de hipótesis da significancia pero no tamaño de efecto (con datasets grandes, hasta cambios triviales son "significativos"). Combinar ambas evita las dos trampas.

**Resultado (última corrida, post-fix):** de 153 comparaciones (17 variables × 9 bloques), 131 estables, 14 en vigilancia, 8 en alerta. Las alertas se concentran en `number_diagnoses_capped` y `admission_type_grp`, y aparecen recién desde el bloque 7-8 en adelante — consistente con el hallazgo de `notebooks/03_preprocesamiento.ipynb` de que el número de diagnósticos cambia su régimen de codificación hacia el final del periodo de estudio. Tabla completa: `resultados/drift_por_bloque.csv`; heatmap: `resultados/fig_psi_heatmap.png`.

## 4. Mapeo de degradación — Experimento E1 (concept drift real)

El modelo principal (elegido en Fase 3 por mejor PR-AUC promedio) se entrena **una sola vez** sobre los bloques 1-2 y se evalúa, sin reentrenar, en los bloques 3-10. Se registran ROC-AUC, PR-AUC, Brier, BSS, pendiente/intercepto de calibración y ECE por bloque, con intervalos de confianza al 95% (bootstrap, B=500). Ver `resultados/fase3_res_e1.csv` y `resultados/fig_E1_degradacion.png`.

## 5. Estrategias de adaptación — Sección 8

Se implementan y comparan 4 estrategias sobre los mismos bloques de prueba:

| Estrategia | Cómo actualiza el modelo | Analogía con la clase |
|---|---|---|
| **E1 — estático** | Nunca se reentrena (baseline "desplegar y olvidar") | — |
| **E2 — expansiva** | En cada bloque, reentrena con *todo* el historial hasta ahí | Ventana creciente |
| **E3 — deslizante** | Reentrena con una ventana fija de $S$ bloques ($S \in \{1,2,3,5\}$ probados) | "Olvido" (forgetting), cuadrante Modelo único × Evolutivo de la diapositiva de estrategias |
| **E4 — disparador** | Parte del modelo estático y solo reentrena cuando se cumple un criterio de disparo (ver abajo) | "Detectores", cuadrante Modelo único × Con triggers |

**Criterio de disparo de E4** (función `disparador`, evaluado bloque a bloque contra la referencia del modelo vigente):
1. Caída de ROC-AUC > 0.03 **y** los intervalos de confianza al 95% no se solapan (evita disparar por ruido), **o**
2. Pendiente de calibración fuera de `[0.80, 1.20]`, **o**
3. PSI > 0.25 en ≥ 2 de 5 variables clave (`number_inpatient`, `num_medications`, `insulin`, `number_diagnoses_capped`, `diag_1_grp`).

Esto combina los dos enfoques de detección de la clase: **basado en tasa de error** (criterios 1-2: ADWIN/Page-Hinkley miden justo esto) y **basado en distribución** (criterio 3: PSI/KS). En el horizonte evaluado se disparó **1 reentrenamiento**.

> **Nota importante:** una versión anterior de la documentación del proyecto describía el disparador como *"el F1-score cae más de 0.05 puntos"*. Eso no es lo que hace el código — el proyecto no calcula F1-score en ningún notebook. Ver `README_CAMBIOS.md` §3.1 para el detalle de esta corrección.

**Resultado:** sobre los bloques comunes a todas las estrategias (6-10), **E3 con $S=3$** obtiene el mejor PR-AUC promedio entre E1/E2/E3 (0.226) y se elige como estrategia desplegada para la capa de decisión. Coincide, sin haberlo forzado, con la ventana de reentrenamiento de tamaño 3 que ya proponía el plan de trabajo original. Tabla: `resultados/experimentos_E1_E4.csv`; figura: `resultados/fig_E1_E4_estrategias.png`.

## 6. Granularidad del monitoreo — Sección 9

Pregunta: ¿una ventana más fina detecta el drift antes, a costa de entrenar con menos datos (más ruido)? Se repite E1 vs. E3 con $G \in \{5, 10, 15\}$ bloques (en vez de los 10 de referencia). Resultado en `resultados/granularidad.csv` y `resultados/fig_granularidad.png`.

## 7. Capa de decisión (costos, incertidumbre, equidad) — Secciones 10-11

No es estrictamente "drift", pero consume directamente sus resultados: el umbral de decisión ($t_1$: Bajo→Moderado, $t_2$: Moderado→Alto) se deriva de una matriz de costos ($C_r$ = costo de un reingreso, $C_i$ = costo de intervenir, $e$ = eficacia de la intervención) y se recalibra por bloque bajo la estrategia elegida (E3, $S=3$). La incertidumbre se estima con réplicas bootstrap del modelo (10 réplicas por ventana); si el intervalo de confianza de una predicción cruza $t_1$ o $t_2$, se marca "Incertidumbre Alta" para revisión médica obligatoria.

## 8. Caso de negocio — Sección 14 (nuevo esta sesión)

**Pregunta que responde:** ¿el módulo de monitoreo de drift se paga solo?

**Método:** compara, bloque a bloque, el costo esperado por cada 1,000 altas bajo dos políticas:
- **Sin monitoreo:** modelo entrenado una vez (bloques 1-2), umbrales de decisión fijados una vez, nunca se vuelven a tocar.
- **Con monitoreo:** la estrategia adaptativa elegida (E3, $S=3$), tal como la dispara el módulo de drift.

**Resultado (con el supuesto ilustrativo de 50,000 altas/año, ver limitaciones):**

| Concepto | Valor anual |
|---|---|
| Costo esperado sin monitoreo | \$90,268,164 |
| Costo esperado con monitoreo adaptativo | \$89,879,592 |
| **Ahorro bruto atribuible al monitoreo** | **\$388,573** |
| Costo de mantenimiento (monitoreo + reentrenos) | \$3,406 |
| **Beneficio neto** | **\$385,167** |
| ROI | ~113× |

Lo más revelador no es el promedio sino la tendencia por bloque: el ahorro por cada 1,000 altas crece de **\$924 (bloque 4) a \$15,114 (bloque 10)** — más de 16×. El valor del monitoreo **no es constante**: crece con el tiempo, a medida que el drift se acumula y la brecha entre "modelo que nunca se actualiza" y "modelo que sí se actualiza" se agranda. Esa es, en una frase, la justificación económica de todo este módulo. Detalle completo, metodología del costo de mantenimiento (construido de abajo hacia arriba, no supuesto en cero) y literatura de respaldo en `informe/informe.tex`, Sección 10.

Archivos: `resultados/caso_negocio_resumen.csv`, `resultados/caso_negocio_por_bloque.csv`, `resultados/fig_caso_negocio.png`.

## 9. Limitaciones conocidas del módulo de drift

- **`encounter_id` es un proxy, no una fecha real.** Los tamaños de bloque/ventana calibrados aquí (10 bloques, $S=3$) son válidos para *este* dataset histórico; en producción, con fecha real de alta, hay que recalibrar.
- **El cupo de Alto Riesgo (`K_ALTO=15%`) es global, no por subgrupo.** La razón de selección entre grupos (regla del 80%) da ≈0.38, por debajo de la meta de 0.80 — un cupo global no puede garantizar selección equitativa cuando las tasas base difieren entre grupos (Chouldechova, 2017). Es un **bloqueante de despliegue**, no un detalle menor: antes de producción hay que evaluar cupos estratificados por grupo o post-procesamiento de igualdad de oportunidad (Hardt et al., 2016).
- **El Brier score (0.0963) queda por encima de la meta (≤0.095).** Está acotado por el techo de discriminación del problema (ROC-AUC ≈ 0.67), ya documentado en la literatura de reingreso hospitalario con datos administrativos (Kansagara et al., 2011). No se logró cerrar la brecha ni con recalibración (Platt/Isotonic) ni con ponderación por clase — ver `README_CAMBIOS.md` §2.3-2.4.
- **"Incertidumbre Alta" subió de 21.6% a 37.6%** tras corregir la fuga de `ctx_readmit_rate`. Es intencional/esperado (el modelo ya no tiene un atajo temporal que lo hacía parecer más seguro de sí mismo), pero en la práctica significa que más de un tercio de las predicciones requeriría revisión médica obligatoria bajo el umbral actual — vale la pena revisar si 15% sigue siendo el umbral correcto para "Incertidumbre Alta" una vez que el modelo es honesto sobre cuánto no sabe.
- **El disparador de E4 solo se probó con 1 evento de reentrenamiento** en el horizonte de bloques evaluado — es poca evidencia para validar la sensibilidad/especificidad del disparador en sí; se recomienda simular con series más largas o sintéticas antes de confiar en él para producción.

## 10. Mapa de archivos

| Archivo | Contenido |
|---|---|
| `notebooks/07_drift_monitoreo.ipynb` | Todo el código de este módulo (Secciones 7-14) |
| `resultados/drift_por_bloque.csv` | PSI + p-valor por variable y bloque |
| `resultados/fig_psi_heatmap.png` | Heatmap de PSI |
| `resultados/fase3_res_e1.csv`, `fig_E1_degradacion.png` | Curva de degradación E1 |
| `resultados/experimentos_E1_E4.csv`, `fig_E1_E4_estrategias.png` | Comparación de estrategias |
| `resultados/granularidad.csv`, `fig_granularidad.png` | Estudio de granularidad |
| `resultados/costos_politicas.csv`, `fig_DCA.png` | Capa de decisión / costos |
| `resultados/equidad.csv` | Auditoría de equidad |
| `resultados/caso_negocio_resumen.csv`, `caso_negocio_por_bloque.csv`, `fig_caso_negocio.png` | Caso de negocio (nuevo) |
| `resultados/resumen_criterios.csv` | Tabla final de 23 criterios de aprobación |
| `informe/informe.tex` / `informe.pdf` | Informe narrativo completo con todo lo anterior integrado |
