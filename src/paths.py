"""Rutas centralizadas del proyecto.

Uso desde un notebook (con CWD = notebooks/):
    import sys; sys.path.append("..")
    from src.paths import RAW, PROCESSED, RESULTADOS
    df = pd.read_csv(RAW / "diabetic_data.csv")

Las rutas se anclan a la raíz del repositorio, así funcionan sin importar
desde dónde se ejecute el notebook.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DATA = ROOT / "data"
RAW = DATA / "raw"            # datos crudos, inmutables (EHR)
INTERIM = DATA / "interim"    # salidas intermedias entre etapas
PROCESSED = DATA / "processed"  # train / validacion / test listos para modelar

ARTIFACTS = ROOT / "artifacts"    # modelos serializados + metadata
RESULTADOS = ROOT / "resultados"  # figuras y tablas finales

for _p in (RAW, INTERIM, PROCESSED, ARTIFACTS, RESULTADOS):
    _p.mkdir(parents=True, exist_ok=True)
