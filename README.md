# grills-diabeticas

Sistema Inteligente Adaptativo para la Predicción de Reingreso Hospitalario
(UTEC 2026 — Planificación y Toma de Decisiones en IA). Dataset UCI *Diabetes
130-US hospitals*.

## Estructura

```
data/
  raw/         # datos crudos e inmutables (diabetic_data.csv, IDS_mapping.csv)
  interim/     # salidas intermedias entre etapas
  processed/   # train / validacion / test + metadata + auditoría de leakage
notebooks/     # un notebook por etapa del pipeline (ver abajo)
src/           # código reutilizable (p. ej. src/paths.py con las rutas)
artifacts/     # modelos serializados
resultados/    # figuras y tablas finales
documents/     # enunciado del proyecto
```

## Notebooks ↔ pipeline

| Notebook | Etapa del diagrama | Estado |
|----------|--------------------|--------|
| `01_ingesta.ipynb` | ① Data Ingestion (EHR) | **hecho** — carga, auditoría de calidad, eje temporal y objetivo → `data/interim/ingesta.pkl` |
| `02_eda.ipynb` | exploración *(dev, fuera del runtime)* | **hecho** — solo EDA; lee `ingesta.pkl` |
| `03_preprocesamiento.ipynb` | ② Cleaning / Normalization / Encoding + leakage + split | **hecho** — lee `ingesta.pkl` → `data/processed/` |
| `04_modelado.ipynb` | ③ Adaptive Predictive Model | **hecho** |
| `05_calibracion_incertidumbre.ipynb` | ④ Uncertainty + Probability Calibration | **hecho** — Platt (train→val) + incertidumbre bootstrap → `artifacts/modelo_calibrado.pkl`, `resultados/scores_test.csv` |
| `06_decision_accion.ipynb` | ⑤ Decision Making + ⑥ Clinical Action | **hecho** — umbrales/costos/DCA/equidad sobre test → `resultados/06_costos_politicas.csv`, `06_equidad.csv`, `06_DCA.png` |
| `07_drift_monitoreo.ipynb` | Concept Drift + feedback retraining | **hecho** — monitoreo de drift + su análisis de decisión por bloque |

Cada notebook lee la salida en disco del anterior; se ejecutan en orden y de forma
independiente. Se corren desde la carpeta `notebooks/` (las rutas usan `../data/...`),
o vía `from src.paths import RAW, PROCESSED, RESULTADOS`.

> El monolito `reingreso_diabetes_pipeline.ipynb` (raíz, en `.gitignore`) queda como
> scratchpad; la fuente de verdad son los notebooks numerados.
