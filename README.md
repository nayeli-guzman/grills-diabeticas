# grills-diabeticas

Sistema Inteligente Adaptativo para la Predicción de Reingreso Hospitalario en Pacientes Diabéticos (UTEC 2026-2 — Planificación y Toma de Decisiones en IA). Dataset: [Diabetes 130-US hospitals for years 1999–2008](https://archive.ics.uci.edu/dataset/296) (UCI).

> Hagan push de lo q avanzan o ya verán 🔪🔪🔪

## Estructura

```
data/
  raw/         # datos crudos e inmutables (diabetic_data.csv, IDS_mapping.csv)
  interim/     # salidas intermedias entre etapas (ingesta.pkl)
  processed/   # train / validacion / test + metadata + auditoría de leakage
notebooks/     # un notebook por etapa del pipeline (ver abajo)
src/           # código reutilizable (src/paths.py con las rutas centralizadas)
artifacts/     # modelos serializados (modelo_calibrado.pkl)
resultados/    # figuras y tablas finales
informe/       # informe completo en LaTeX (.tex + .pdf)
documents/     # enunciado del proyecto
```

## Notebooks ↔ pipeline

| Notebook | Etapa del diagrama de arquitectura | Qué hace |
|----------|--------------------------------------|----------|
| `01_ingesta.ipynb` | ① Data Ingestion (EHR) | Carga, auditoría de calidad, eje temporal (`t_idx`, `period`) y objetivo → `data/interim/ingesta.pkl` |
| `02_eda.ipynb` | exploración *(dev, no forma parte del runtime)* | Solo EDA descriptivo; lee `ingesta.pkl` |
| `03_preprocesamiento.ipynb` | ② Feature Preprocessing + auditoría de leakage + split | Limpieza, features, **auditoría de fuga de información (13 pruebas)**, split temporal con embargo calibrado → `data/processed/` |
| `04_modelado.ipynb` | ③ Adaptive Predictive Model | ElasticNet / Random Forest / XGBoost, tuning temporal, curva de degradación E1 → `resultados/fase3_modelo.json` |
| `05_calibracion_incertidumbre.ipynb` | ④ Uncertainty Evaluator + Probability Calibration | Calibración Platt sobre el split train→validación→test + incertidumbre bootstrap → `artifacts/modelo_calibrado.pkl`, `resultados/scores_test.csv` |
| `06_decision_accion.ipynb` | ⑤ Decision Making + ⑥ Clinical Action | Umbrales por matriz de costos, categorías de riesgo, DCA, equidad — sobre el split estándar |
| `07_drift_monitoreo.ipynb` | Concept Drift Monitoring (retroalimentación) | Monitoreo de drift por ventanas fijas (PSI/KS), estrategias de adaptación E1–E4, capa de decisión **por bloque pseudo-temporal**, equidad, SHAP y **caso de negocio** |

Cada notebook lee la salida en disco del anterior; se ejecutan en orden desde la carpeta `notebooks/` (rutas relativas `../data/...`, `../resultados/...`, o vía `from src.paths import RAW, PROCESSED, RESULTADOS`). `07_drift_monitoreo.ipynb` es el más completo: repite el análisis de calibración/decisión de `05`/`06` pero simulando producción real a lo largo de 10 bloques pseudo-temporales en vez de un único split estático — es la fuente de verdad para todo lo que es data/concept drift.

> Nota de kernel: `07_drift_monitoreo.ipynb` tiene guardado un kernel llamado `diabetes-reingreso` que no existe en un entorno nuevo. Ejecutarlo con `--ExecutePreprocessor.kernel_name=python3` o registrar ese kernel con `python -m ipykernel install --name diabetes-reingreso`.

## Documentación

| Documento | Contenido |
|---|---|
| [`informe/informe.pdf`](informe/informe.pdf) (`.tex` fuente en la misma carpeta) | Informe completo: problema, objetivos, arquitectura, modelado, drift, equidad, caso de negocio (síntesis), bibliografía |
| [`README_DATA_DRIFT.md`](README_DATA_DRIFT.md) | Documentación técnica del módulo de data/concept drift: metodología, estrategias E1–E4, resultados, **limitaciones conocidas** |
| [`README_CASO_NEGOCIO.md`](README_CASO_NEGOCIO.md) | Caso de negocio explicado a fondo: de dónde sale cada número, por qué el ahorro crece con el tiempo, qué queda fuera del cálculo |
| [`README_CAMBIOS.md`](README_CAMBIOS.md) | Registro de los fixes de fuga de información y de la fusión con la reorganización de `notebooks/` |

## Estado de las métricas de éxito (última corrida)

**18 de 23 criterios cuantitativos se cumplen.** Los 5 que no, con su explicación y mitigación propuesta, están documentados en detalle en [`README_DATA_DRIFT.md` §9](README_DATA_DRIFT.md#9-limitaciones-conocidas-del-módulo-de-drift) y en la Sección 13.1 del informe:

- **Brier score** (0.0963 vs. meta ≤0.095) — acotado por el techo de discriminación del problema (ROC-AUC ≈0.67), consistente con la literatura de reingreso hospitalario.
- **Costo esperado, escenario de sensibilidad e=0.38** — pierde por un margen pequeño frente a "intervenir a todos" solo en ese escenario extremo/optimista.
- **Impacto proyectado** (3.8% vs. meta ≥5%) — mismo techo de discriminación.
- **Incertidumbre Alta** (37.6% vs. meta ≤15%) — subió tras corregir un leak que hacía al modelo parecer artificialmente más seguro de sí mismo; ver nota en `README_DATA_DRIFT.md`.
- **Razón de selección / regla del 80%** (0.38 vs. meta ≥0.80) — **bloqueante de despliegue**: el cupo de Alto Riesgo es global y no garantiza selección equitativa entre subgrupos. Requiere cupos estratificados o post-procesamiento de igualdad de oportunidad antes de producción.

Requisitos: `pip install -r requirements.txt`.
