"""Helper para ejecutar queries SQL versionadas en `sql/` con DuckDB.

DuckDB se elige porque:
- Lee Parquet directo sin servidor (`read_parquet('archivo.parquet')`).
- SQL moderno PostgreSQL-compatible (window functions, CTEs, lateral joins).
- En proceso, sin infraestructura, ideal para CI y desarrollo local.

Patrón de uso:

    from transporte.sql_runner import run_query

    df = run_query(
        "sql/gold/kpi_entregas.sql",
        params={"silver_dir": "data/processed"},
    )

Las queries pueden referenciar parámetros con `$nombre` (sintaxis DuckDB
prepared statement) o con placeholders Python `{nombre}` (formateado por
str.format antes de ejecutar). El helper resuelve ambos.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = REPO_ROOT / "sql"


def read_query(path: str | Path) -> str:
    """Lee el contenido de un .sql relativo al repo o absoluto."""
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    if not p.exists():
        msg = f"Query SQL no encontrada: {p}"
        raise FileNotFoundError(msg)
    return p.read_text(encoding="utf-8")


def run_query(
    path: str | Path,
    *,
    params: dict[str, Any] | None = None,
    con: duckdb.DuckDBPyConnection | None = None,
) -> pd.DataFrame:
    """Ejecuta el SQL en `path` y devuelve el resultado como DataFrame.

    - `params`: dict para sustitución de placeholders `{nombre}` en el texto
      del SQL antes de enviarlo a DuckDB. Útil para parametrizar rutas de
      Parquet sin meter strings hardcoded en el .sql.
    - `con`: conexión DuckDB existente (ideal en tests). Si es None, se crea
      una efímera in-memory.
    """
    sql = read_query(path)
    if params:
        sql = sql.format(**params)

    log.info("Ejecutando SQL %s", path)
    own_con = con is None
    if own_con:
        con = duckdb.connect(database=":memory:")
    try:
        result = con.execute(sql).df()
    finally:
        if own_con:
            con.close()
    log.info("  -> %s filas, %s cols", len(result), result.shape[1])
    return result


def silver_dir_for_sql(silver_dir: Path) -> str:
    """Convierte una ruta absoluta a string POSIX para interpolar en SQL.

    En Windows las rutas tienen `\\` que rompen string literals SQL. POSIX
    funciona en ambos sistemas (DuckDB acepta forward slashes en Windows).
    """
    return Path(silver_dir).resolve().as_posix()
