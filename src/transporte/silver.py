"""Capa Silver: tipa, limpia y enriquece los datos Bronze.

Lee los parquets producidos por `transporte.bronze` y produce dos parquets
Silver con tipos correctos, columnas en snake_case, normalización de texto
y KPIs operativos básicos calculados (`dias_retraso`, `entrega_on_time`,
`flag_no_entregado`, `dias_hasta_devolucion`).

Silver es la capa "confiable para analytics": cualquier consulta o
visualización aguas abajo puede asumir tipos correctos, sin valores
sucios y con la lógica de negocio mínima ya aplicada.

Uso CLI:

    uv run python -m transporte.silver \\
        --input-dir data/processed \\
        --output-dir data/processed

Uso programático:

    from transporte.silver import silverize_all
    silverize_all()
"""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from transporte import schemas

log = logging.getLogger(__name__)

DEFAULT_DIR = Path("data/processed")

INPUT_VIAJES = "bronze_viajes.parquet"
INPUT_DEVOLUCIONES = "bronze_devoluciones.parquet"
OUTPUT_VIAJES = "silver_viajes.parquet"
OUTPUT_DEVOLUCIONES = "silver_devoluciones.parquet"

VIAJES_RENAMES: dict[str, str] = {
    "Suborden": "suborden",
    "Do": "documento",
    "Estado": "estado",
    "Patente": "patente",
    "Empresa": "empresa",
    "Idruta": "id_ruta",
    "Posicionruta": "posicion_ruta",
    "Ct": "centro_transporte",
    "Direccion": "direccion",
    "Localidad": "localidad",
    "Region": "region",
    "Volumen": "volumen_raw",
    "Horainicio": "hora_inicio",
    "Horafin": "hora_fin",
    "Fechainicioruta": "fecha_inicio_ruta",
    "Fechapactada": "fecha_pactada",
    "Fechaentregareal": "fecha_entrega_real",
    "Fechaestimada": "fecha_estimada",
    "Comentarionoentrega": "comentario_no_entrega",
    "Motivonoentrega": "motivo_no_entrega",
    "LPN": "lpn",
    "LPN_Container": "lpn_container",
    "Commerce": "commerce",
    "ParentOrder": "parent_order",
    "Activa": "activa",
}

VIAJES_FECHAS = ("fecha_inicio_ruta", "fecha_pactada", "fecha_entrega_real", "fecha_estimada")
DEVOLUCIONES_FECHAS = ("fecha_viaje", "fecha_devolucion")
DEVOLUCIONES_TEXTO = ("seller", "observaciones", "estado_recepcion", "estado_devolucion", "patente")

ESTADO_TERMINADO = "Terminado"


def _drop_bronze_metadata(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop(columns=[c for c in df.columns if c.startswith("_")])


def _parse_dates(df: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        out[col] = pd.to_datetime(out[col], errors="coerce")
    return out


def _parse_volumen(volumen_raw: pd.Series) -> pd.Series:
    return pd.to_numeric(
        volumen_raw.astype(str).str.replace('"', "", regex=False).str.strip(),
        errors="coerce",
    )


def _parse_activa(activa_raw: pd.Series) -> pd.Series:
    """Convierte la columna activa (string 'True'/'False') a booleano nullable."""
    mapping = {"True": True, "False": False, "true": True, "false": False}
    return activa_raw.astype(str).map(mapping).astype("boolean")


def _normalize_text(series: pd.Series, *, title_case: bool = True) -> pd.Series:
    cleaned = series.astype(str).str.strip()
    return cleaned.str.title() if title_case else cleaned


def transform_viajes(bronze_df: pd.DataFrame) -> pd.DataFrame:
    """Convierte un DataFrame Bronze de viajes a Silver."""
    df = bronze_df.rename(columns=VIAJES_RENAMES)
    df = _drop_bronze_metadata(df)
    df = _parse_dates(df, VIAJES_FECHAS)

    df["volumen"] = _parse_volumen(df["volumen_raw"])
    df = df.drop(columns=["volumen_raw"])

    df["activa"] = _parse_activa(df["activa"])
    df["estado"] = _normalize_text(df["estado"], title_case=True)
    df["region"] = _normalize_text(df["region"], title_case=False)
    df["commerce"] = _normalize_text(df["commerce"], title_case=True)

    df["dias_retraso"] = (
        (df["fecha_entrega_real"] - df["fecha_pactada"]).dt.days.astype("Float64")
    )
    df["entrega_on_time"] = (df["dias_retraso"] <= 0).astype(int)
    df["flag_no_entregado"] = (df["estado"] != ESTADO_TERMINADO).astype(int)

    df["_silver_timestamp"] = datetime.now(tz=UTC).isoformat()
    schemas.validate(df, schemas.SILVER_VIAJES_SCHEMA, name="silver_viajes")
    return df


def transform_devoluciones(bronze_df: pd.DataFrame) -> pd.DataFrame:
    """Convierte un DataFrame Bronze de devoluciones a Silver."""
    df = _drop_bronze_metadata(bronze_df)
    df = _parse_dates(df, DEVOLUCIONES_FECHAS)

    for col in DEVOLUCIONES_TEXTO:
        if col in df.columns:
            df[col] = _normalize_text(df[col], title_case=True)

    df["dias_hasta_devolucion"] = (
        (df["fecha_devolucion"] - df["fecha_viaje"]).dt.days.astype("Float64")
    )
    df["_silver_timestamp"] = datetime.now(tz=UTC).isoformat()
    schemas.validate(df, schemas.SILVER_DEVOLUCIONES_SCHEMA, name="silver_devoluciones")
    return df


def _read_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        msg = f"Falta el parquet Bronze esperado en {path}. Corre transporte.bronze antes."
        raise FileNotFoundError(msg)
    log.info("Leyendo %s", path)
    df = pd.read_parquet(path, engine="pyarrow")
    log.info("  %s filas", len(df))
    return df


def _write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, engine="pyarrow", index=False)
    log.info("  -> %s (%s filas, %s cols)", path, len(df), df.shape[1])


def silverize_viajes(input_dir: Path, output_dir: Path) -> Path:
    bronze_df = _read_parquet(input_dir / INPUT_VIAJES)
    silver_df = transform_viajes(bronze_df)
    output_path = output_dir / OUTPUT_VIAJES
    _write_parquet(silver_df, output_path)
    return output_path


def silverize_devoluciones(input_dir: Path, output_dir: Path) -> Path:
    bronze_df = _read_parquet(input_dir / INPUT_DEVOLUCIONES)
    silver_df = transform_devoluciones(bronze_df)
    output_path = output_dir / OUTPUT_DEVOLUCIONES
    _write_parquet(silver_df, output_path)
    return output_path


def silverize_all(
    input_dir: Path = DEFAULT_DIR,
    output_dir: Path = DEFAULT_DIR,
) -> dict[str, Path]:
    """Procesa ambas tablas Bronze a Silver."""
    log.info("Silver transform | input_dir=%s | output_dir=%s", input_dir, output_dir)
    return {
        "viajes": silverize_viajes(input_dir, output_dir),
        "devoluciones": silverize_devoluciones(input_dir, output_dir),
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="transporte.silver",
        description="Capa Silver: limpia, tipa y enriquece los Parquets Bronze.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_DIR,
        help=f"Directorio con parquets Bronze (default: {DEFAULT_DIR}).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_DIR,
        help=f"Directorio donde escribir parquets Silver (default: {DEFAULT_DIR}).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    outputs = silverize_all(input_dir=args.input_dir, output_dir=args.output_dir)
    log.info("Silver transform OK: %s", {k: str(v) for k, v in outputs.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
