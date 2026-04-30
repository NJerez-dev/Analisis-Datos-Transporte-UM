# Notebooks legacy

Versión original del análisis (pre-refactor). Se conservan como **referencia histórica** mientras dura el refactor en `refactor/de-grade`.

No editar estos archivos. Para la lógica refactorizada ver `src/transporte/` y los notebooks nuevos en `notebooks/` (cuando existan).

## Mapping

| Notebook legacy | Reemplazado por |
|---|---|
| `01_bronze_ingesta.ipynb` | `src/transporte/bronze.py` (TBD) |
| `02_silver_transformacion.ipynb` | `src/transporte/silver.py` (TBD) |
| `03_gold_kpis.ipynb` | `src/transporte/gold.py` (TBD) |

Una vez fusionado el refactor a `main` y verificado que el pipeline nuevo replica resultados, este directorio se puede archivar o borrar.
