"""Pipeline de análisis de transporte de última milla con arquitectura medallón.

Capas:
    - `transporte.bronze`: ingesta cruda Excel → Parquet (sin tipado).
    - `transporte.silver`: limpieza, tipado y joins (TBD).
    - `transporte.gold`: KPIs operativos (TBD).
"""

from transporte import bronze, silver

__all__ = ["bronze", "silver"]


def main() -> None:
    """Entry point por defecto del paquete: corre el pipeline bronze.

    Se ejecuta cuando alguien llama `transporte` como CLI (definido en
    `pyproject.toml` como entry point del proyecto). Cada capa también puede
    invocarse independiente con `python -m transporte.bronze`, etc.
    """
    raise SystemExit(bronze.main())
