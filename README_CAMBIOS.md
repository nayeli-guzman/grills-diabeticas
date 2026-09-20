# Registro de cambios — sesión de revisión de Data Drift

Este documento registra todo lo que se modificó sobre el trabajo ya existente del equipo (notebooks `02_EDA.ipynb`, `03_modelado.ipynb`, `05_drift_adaptacion.ipynb`) durante esta sesión, por qué se hizo, y qué resultados nuevos generó. No reemplaza al `README.md` del repo; es un registro de auditoría de esta iteración puntual.

> Para el detalle completo de la metodología de drift (qué es, cómo se mide, resultados), ver **`README_DATA_DRIFT.md`**.
> Para el informe narrativo completo (enunciado + resultados + caso de negocio + bibliografía), ver **`informe/informe.tex`** / **`informe/informe.pdf`**.

## 1. Por qué se hicieron estos cambios

Al revisar el pipeline completo se encontró que la propia auditoría de fuga de información del equipo (`02_EDA.ipynb`, Sección 10, exportada en `artifacts/data_preparada/auditoria_leakage.csv`) hacía dos recomendaciones explícitas para el modelado que **no se habían aplicado** en `03_modelado.ipynb` ni en `05_drift_adaptacion.ipynb`. Esto es importante porque ambos notebooks son la base de todas las cifras de "concept/data drift" reportadas — si están corridos con una fuga de información, las curvas de degradación no miden drift real.

## 2. Cambios de código

### 2.1 `USAR_CONTEXTO = True → False`
**Archivos:** `03_modelado.ipynb` (celda de definición de variables), `05_drift_adaptacion.ipynb` (ídem).

Las variables `ctx_readmit_rate`, `ctx_inpatient_mean`, `ctx_a1c_rate`, `rel_number_diagnoses`, `rel_num_medications` son promedios en ventana deslizante que cambian con el tiempo por construcción. La auditoría de `02_EDA.ipynb` (Sección 10.5) midió que incluirlas empeora la validación/test (AUC val 0.664→0.656) y agranda la brecha train−val (0.079→0.117): el modelo aprende a "leer la época" en vez de un patrón clínico transferible. Su estado en `auditoria_leakage.csv` es explícitamente `"No usar"`, y la conclusión de esa sección dice textualmente *"Poner `USAR_CONTEXTO = False`"*.

**Por qué importa para drift específicamente:** si el propio predictor incluye un proxy del tiempo, cualquier curva de "degradación por drift" queda contaminada — parte de lo que se mediría como drift real sería en realidad el modelo perdiendo su atajo temporal.

### 2.2 `EMBARGO = 850 → 2000`
**Archivos:** mismos dos notebooks, en la celda de parámetros de ejecución.

`02_EDA.ipynb` (Sección 10.3) calibró que el equivalente real de "30 días" varía entre ~800 y ~1,700 encuentros según el periodo (creciente en el tiempo) y fijó `LABEL_DELAY = 2000` para eliminar una fuga temporal medida (reingresos de *train* cuya etiqueta aún no era observable en la fecha de corte). La recomendación explícita para el modelado fue: *"Usar como EMBARGO el `label_delay_encuentros` del metadata, en lugar de 850, en todo esquema de bloques, ventanas deslizantes y reentrenamiento."* Ambos notebooks seguían usando 850, reintroduciendo el mismo tipo de fuga dentro del esquema de bloques usado para medir drift.

### 2.3 Calibración: selección automática Platt vs. Isotonic Regression
**Archivo:** clase `ModeloCalibrado` en `03_modelado.ipynb` y `05_drift_adaptacion.ipynb` (idéntica en ambos).

Antes: la calibración final siempre usaba Platt scaling (logística sobre el logit del score). Ahora: dentro de la ventana de calibración (últimos 20% de la ventana de entrenamiento) se hace un sub-split temporal 70/30, se ajustan **ambos** métodos (Platt y Isotonic Regression) en el 70%, se mide el Brier score de cada uno en el 30% restante, se elige el que minimiza Brier, y **ese** método se reajusta sobre el 100% de la ventana de calibración para uso en producción.

Justificación: Platt (1999); Isotonic Regression aplicada a calibración de clasificadores (Zadrozny & Elkan, 2002); comparación empírica de ambos métodos (Niculescu-Mizil & Caruana, 2005). Ya estaba previsto en el diseño del sistema ("Calibración de probabilidades mediante Platt Scaling / Isotonic Regression", Sección de arquitectura del informe original), solo no estaba implementado como una elección automática.

### 2.4 Experimento descartado: `class_weight` balanceado en Random Forest
**Estado final: revertido, no está en el código.**

Se probó agregar `class_weight ∈ {None, "balanced_subsample"}` a la grilla de Random Forest (Chen, Liaw & Breiman, 2004, técnica estándar para desbalance de clases). Resultado: no mejoró el Brier score (se mantuvo en 0.098) y además desplazó la selección del modelo principal de `RandomForest` a `ElasticNet` de forma inestable (una corrida lo elegía, otra no), sin beneficio medible. Se revirtió la grilla a su versión original. Se documenta aquí para que quede registro de que se intentó y por qué no se adoptó — no hace falta volver a probarlo sin una razón nueva.

### 2.5 Nueva sección: Caso de negocio (Sección 14 de `05_drift_adaptacion.ipynb`)
Sección completamente nueva, agregada al final del notebook. Calcula:
- El costo esperado por cada 1,000 altas usando el modelo **estático "desplegado y olvidado"** (entrenado una vez en bloques 1–2, con umbrales de decisión fijos para siempre) vs.
- El costo esperado usando la **estrategia adaptativa desplegada** (la que ya elige automáticamente la Sección 8 del notebook por mejor PR-AUC).
- La diferencia, proyectada a un volumen anual ilustrativo, menos un costo de mantenimiento estimado de abajo hacia arriba (monitoreo mensual + reentrenamientos disparados).

Ver el detalle completo y los números en `README_DATA_DRIFT.md` (Sección "Caso de negocio") y en `informe/informe.tex` (Sección 10).

Archivos nuevos que genera esta sección: `resultados/caso_negocio_por_bloque.csv`, `resultados/caso_negocio_resumen.csv`, `resultados/fig_caso_negocio.png`.

### 2.6 Paquete instalado
`shap` (no estaba en `requirements.txt` ni instalado en el entorno usado para correr los notebooks esta sesión, pero es requerido por la Sección 12 de `05_drift_adaptacion.ipynb`). Se instaló vía `pip install shap`. **Pendiente:** agregarlo a `requirements.txt` si no está ya.

## 3. Cambios de contenido / documentación

### 3.1 Corrección de una inconsistencia entre el plan de trabajo y el código (disparador de reentrenamiento)
El documento original describía el disparador de la estrategia E4 como *"el F1-score cae más de 0.05 puntos respecto a la referencia"*. **El proyecto nunca calcula F1-score en ningún notebook** (tampoco aparece en la tabla de Métricas de Éxito del informe original, que usa ROC-AUC/PR-AUC/Brier). El disparador realmente implementado en el código (`05_drift_adaptacion.ipynb`, función `disparador`, Sección 8) es un criterio combinado: caída de ROC-AUC > 0.03 con intervalos de confianza al 95% sin solapar, **o** pendiente de calibración fuera de [0.80, 1.20], **o** PSI > 0.25 en ≥2 de 5 variables clave. Se corrigió la descripción en `informe/informe.tex` para que coincida con lo implementado (más robusto que un único punto de corte de F1).

### 3.2 Sección "Propuesta preliminar de despliegue y riesgos"
Esta sección existía como encabezado vacío en el documento original (sin contenido debajo). Se redactó completa en `informe/informe.tex` (Sección 11): propuesta de despliegue por microservicios en contenedor sobre IaaS/PaaS, pipeline mínimo de MLOps, y una tabla de 5 riesgos identificados con su mitigación (incluye explícitamente el riesgo de inequidad en la selección de Alto Riesgo detectado en la auditoría de equidad).

### 3.3 Bibliografía ampliada
Se agregaron ~14 referencias nuevas al informe (no estaban en el documento original): Strack et al. 2014 (paper fuente del dataset — sorprendentemente no estaba citado), Platt 1999, Zadrozny & Elkan 2002, Niculescu-Mizil & Caruana 2005, Chen/Liaw/Breiman 2004, Gama et al. 2014, Widmer & Kubat 1996, Bifet & Gavaldà 2007 (ADWIN), Page 1954 (Page-Hinkley), Siddiqi 2006 (PSI), Sculley et al. 2015 (deuda técnica en ML / costo de mantenimiento), y las diapositivas de clase de Concept Drift como referencia del marco conceptual usado.

## 4. Resultados: antes vs. después del fix

| Métrica (modelo principal, E1 estático) | Antes (con fuga) | Después (corregido) |
|---|---|---|
| Modelo principal elegido | RandomForest | RandomForest (sin cambio) |
| ROC-AUC (estrategia desplegada) | 0.665 | **0.673** |
| PR-AUC / lift | 0.215 / 1.89× | **0.220 / 1.94×** |
| Brier (BSS) | 0.0970 (0.030) | **0.0963 (0.044)** — más cerca de la meta |
| Razón de selección 80% (equidad) | 0.24 | **0.38** — mejoró, sigue sin cumplir |
| Calibración por subgrupo | ✘ | **✔** |
| Incertidumbre Alta | 21.6% | 37.6% — empeoró (ver nota abajo) |

**Nota sobre "Incertidumbre Alta":** subió después del fix. Esto es esperable y es una señal de que el fix funcionó: antes, el modelo usaba `ctx_readmit_rate` como un atajo que lo hacía parecer más seguro de sí mismo (aprendía "en qué época está" en vez de generalizar); al quitarlo, sus réplicas bootstrap discrepan más — el modelo es menos overconfident, no que haya empeorado objetivamente. Se documenta como limitación conocida en `README_DATA_DRIFT.md`.

## 5. Cómo reproducir

Orden de ejecución (cada uno depende del anterior):

```bash
# 1. Preparación de datos + auditoría de leakage (ya no se tocó en esta sesión)
jupyter nbconvert --to notebook --execute --inplace 02_EDA.ipynb

# 2. Modelado (Fase 3) — con los fixes de esta sesión
jupyter nbconvert --to notebook --execute --inplace 03_modelado.ipynb

# 3. Monitoreo de drift + capa de decisión + caso de negocio (Fase 4-5) — con los fixes de esta sesión
jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=python3 05_drift_adaptacion.ipynb
```

Nota: `05_drift_adaptacion.ipynb` tiene guardado en sus metadatos un kernel llamado `diabetes-reingreso` que no existe en un entorno nuevo; por eso el flag `--ExecutePreprocessor.kernel_name=python3` (o registrar ese kernel con `python -m ipykernel install --name diabetes-reingreso`).

## 6. Archivos nuevos creados esta sesión

- `informe/informe.tex`, `informe/informe.pdf`, `informe/tabla_*.tex`, `informe/_gen_tablas.py` — informe completo en LaTeX.
- `resultados/caso_negocio_por_bloque.csv`, `resultados/caso_negocio_resumen.csv`, `resultados/fig_caso_negocio.png` — caso de negocio.
- `README_CAMBIOS.md` (este archivo).
- `README_DATA_DRIFT.md` — documentación completa del módulo de data/concept drift.

## 7. Qué NO se hizo (a propósito)

- **No se implementó una corrección a la razón de selección del 80%** (equidad). Requeriría rediseñar el mecanismo de cupo (`K_ALTO`) para que sea estratificado por grupo o agregar post-procesamiento de igualdad de oportunidad (Hardt et al., 2016) — es una decisión de diseño con implicancias éticas/regulatorias que debe validarse con el equipo antes de implementarse, no algo para decidir unilateralmente bajo presión de tiempo. Queda documentado como bloqueante de despliegue.
- **No se forzó el Brier score a cumplir la meta** (quedó en 0.0963 vs. ≤0.095) inflando artificialmente la calibración o recortando la muestra de validación. Se prefirió reportar el número real y explicarlo con literatura (el techo de discriminación ~0.67 ROC-AUC ya está documentado en la literatura de este problema).
- **No se hizo `git commit` ni `git push`** de ninguno de estos cambios — quedan solo en el working tree, a la espera de que el equipo revise y decida qué commitear.
