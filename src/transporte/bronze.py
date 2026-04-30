"""Capa Bronze: ingesta cruda del Excel fuente a Parquet.

Bronze preserva los datos **como string**, sin inferencia de tipos. La única
transformación permitida es normalizar nombres de columnas con caracteres
no-ASCII a snake_case (necesario para que Parquet y SQL no se quejen).

Toda interpretación de tipos, joins, limpieza y reglas de negocio van en
`transporte.silver`. Bronze es la verdad cruda + metadata de ingesta.

Uso CLI:

    uv run python -m transporte.bronze \\
        --input data/raw/transporte_um.xlsx \\
        --output-dir data/processed

Uso programático:

    from transporte.bronze import ingest_all
    ingest_all(input_path=Path("data/raw/transporte_um.xlsx"))
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

DEFAULT_INPUT = Path("data/raw/transporte_um.xlsx")
DEFAULT_OUTPUT_DIR = Path("data/processed")

SHEET_VIAJES = "VIAJES DIARIOS"
SHEET_DEVOLUCIONES = "DEVOLUCIONES"

OUTPUT_VIAJES = "bronze_viajes.parquet"
OUTPUT_DEVOLUCIONES = "bronze_devoluciones.parquet"

# Renombrado mínimo: solo columnas con caracteres no-ASCII o duplicadas por pandas.
DEVOLUCIONES_RENAMES: dict[str, str] = {
    "N° Recepción": "nro_recepcion",
    "Seller": "seller",
    "Nº de Etiqueta": "nro_etiqueta",
    "Nº de OC": "nro_oc",
    "Estado": "estado_recepcion",
    "Observaciones": "observaciones",
    "Patente": "patente",
    "Fecha viaje": "fecha_viaje",
    "Fecha devolución": "fecha_devolucion",
    "Estado.1": "estado_devolucion",
}


@dataclass(frozen=True)
class IngestionMetadata:
    """Metadata que se anexa como columnas a cada DataFrame Bronze."""

    timestamp: str
    fuente: str
    archivo: str

    @classmethod
    def now(cls, fuente: str, archivo: str) -> IngestionMetadata:
        return cls(
            timestamp=datetime.now(tz=UTC).isoformat(),
            fuente=fuente,
            archivo=archivo,
        )


def read_sheet_as_strings(input_path: Path, sheet_name: str) -> pd.DataFrame:
    """Lee una hoja del Excel preservando todos los valores como string.

    Bronze no infiere tipos. Cualquier conversión a fecha/numérico es
    responsabilidad de Silver.
    """
    if not input_path.exists():
        msg = f"No existe el archivo de entrada: {input_path}"
        raise FileNotFoundError(msg)

    log.info("Leyendo %s | hoja=%s", input_path, sheet_name)
    df = pd.read_excel(input_path, sheet_name=sheet_name, engine="openpyxl", dtype=str)
    log.info("  %s filas, %s columnas", len(df), len(df.columns))
    return df


def add_metadata(df: pd.DataFrame, metadata: IngestionMetadata) -> pd.DataFrame:
    """Anexa columnas `_ingesta_timestamp`, `_fuente`, `_archivo` al DataFrame."""
    out = df.copy()
    out["_ingesta_timestamp"] = metadata.timestamp
    out["_fuente"] = metadata.fuente
    out["_archivo"] = metadata.archivo
    return out


def normalize_column_names(df: pd.DataFrame, renames: dict[str, str]) -> pd.DataFrame:
    """Renombra columnas según el mapping. Las no listadas se mantienen.

    También filtra columnas con header `NaN` que pandas inventa cuando hay
    columnas vacías al final del Excel.
    """
    out = df.loc[:, df.columns.notna()].rename(columns=renames)
    return out


def write_parquet(df: pd.DataFrame, output_path: Path) -> None:
    """Escribe el DataFrame como Parquet, creando el directorio si falta."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, engine="pyarrow", index=False)
    log.info("  -> %s (%s filas)", output_path, len(df))


def ingest_viajes(input_path: Path, output_dir: Path) -> Path:
    """Ingesta la hoja VIAJES DIARIOS y escribe `bronze_viajes.parquet`."""
    metadata = IngestionMetadata.now(fuente=SHEET_VIAJES, archivo=input_path.name)
    df = read_sheet_as_strings(input_path, SHEET_VIAJES)
    df = add_metadata(df, metadata)
    output_path = output_dir / OUTPUT_VIAJES
    write_parquet(df, output_path)
    return output_path


def ingest_devoluciones(input_path: Path, output_dir: Path) -> Path:
    """Ingesta la hoja DEVOLUCIONES y escribe `bronze_devoluciones.parquet`."""
    metadata = IngestionMetadata.now(fuente=SHEET_DEVOLUCIONES, archivo=input_path.name)
    df = read_sheet_as_strings(input_path, SHEET_DEVOLUCIONES)
    df = normalize_column_names(df, DEVOLUCIONES_RENAMES)
    df = add_metadata(df, metadata)
    output_path = output_dir / OUTPUT_DEVOLUCIONES
    write_parquet(df, output_path)
    return output_path


def ingest_all(
    input_path: Path = DEFAULT_INPUT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Path]:
    """Ingesta ambas hojas. Devuelve el mapping nombre lógico → ruta del parquet."""
    log.info("Bronze ingest | input=%s | output_dir=%s", input_path, output_dir)
    return {
        "viajes": ingest_viajes(input_path, output_dir),
        "devoluciones": ingest_devoluciones(input_path, output_dir),
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="transporte.bronze",
        description="Capa Bronze: ingesta del Excel fuente a Parquet.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Ruta al Excel fuente (default: {DEFAULT_INPUT}).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directorio donde escribir los parquets (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Nivel de logging (default: INFO).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    outputs = ingest_all(input_path=args.input, output_dir=args.output_dir)
    log.info("Bronze ingest OK: %s", {k: str(v) for k, v in outputs.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
