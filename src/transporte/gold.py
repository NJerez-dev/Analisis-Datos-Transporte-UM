"""Capa Gold: KPIs operativos y modelo dimensional listos para BI.

Lee los parquets Silver y produce 6 tablas Gold:

| Tabla                    | Granularidad           | Para qué |
|--------------------------|------------------------|----------|
| gold_kpi_entregas        | 1 fila (KPI global)    | Resumen ejecutivo |
| gold_kpi_por_commerce    | 1 fila por cliente     | Performance por retailer |
| gold_kpi_por_patente     | 1 fila por vehículo    | Rendimiento por camión |
| gold_kpi_devoluciones    | 1 fila por motivo      | Causas de devolución |
| gold_dim_tiempo          | 1 fila por día         | Calendario para Power BI |
| gold_fact_viajes         | 1 fila por viaje       | Tabla de hechos |

Salida:
- Parquets en `data/processed/` (consumo programático).
- CSVs UTF-8 BOM en `data/exports/` (Power BI, Excel).

Uso CLI:

    uv run python -m transporte.gold \\
        --input-dir data/processed \\
        --output-dir data/processed \\
        --exports-dir data/exports
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
DEFAULT_EXPORTS_DIR = Path("data/exports")

INPUT_VIAJES = "silver_viajes.parquet"
INPUT_DEVOLUCIONES = "silver_devoluciones.parquet"

ESTADO_TERMINADO = "Terminado"


GOLD_TABLES_ORDER = (
    "gold_kpi_entregas",
    "gold_kpi_por_commerce",
    "gold_kpi_por_patente",
    "gold_kpi_devoluciones",
    "gold_dim_tiempo",
    "gold_fact_viajes",
)

FACT_VIAJES_COLUMNS = (
    "suborden",
    "documento",
    "estado",
    "patente",
    "commerce",
    "id_ruta",
    "posicion_ruta",
    "centro_transporte",
    "localidad",
    "region",
    "volumen",
    "fecha_pactada",
    "fecha_entrega_real",
    "fecha_estimada",
    "dias_retraso",
    "entrega_on_time",
    "flag_no_entregado",
    "motivo_no_entrega",
    "activa",
)


def _now_utc_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def compute_kpi_entregas(viajes: pd.DataFrame, devoluciones: pd.DataFrame) -> pd.DataFrame:
    """KPI global de entregas. Una sola fila."""
    total_viajes = len(viajes)
    terminados = int((viajes["estado"] == ESTADO_TERMINADO).sum())
    on_time = int(viajes["entrega_on_time"].sum())
    pct_on_time = round(viajes["entrega_on_time"].mean() * 100, 2)
    pct_no_entregado = round(viajes["flag_no_entregado"].mean() * 100, 2)
    lead_time = round(viajes["dias_retraso"].mean(), 2)
    total_dev = len(devoluciones)
    tasa_dev = round(total_dev / total_viajes * 100, 2) if total_viajes else 0.0
    rutas = int(viajes["id_ruta"].nunique())
    patentes = int(viajes["patente"].nunique())
    volumen_total = round(float(viajes["volumen"].sum()), 4)

    df = pd.DataFrame(
        [
            {
                "total_viajes": total_viajes,
                "viajes_terminados": terminados,
                "viajes_on_time": on_time,
                "pct_on_time_delivery": pct_on_time,
                "pct_no_entregado": pct_no_entregado,
                "lead_time_dias_prom": lead_time,
                "total_devoluciones": total_dev,
                "tasa_devolucion_pct": tasa_dev,
                "rutas_unicas": rutas,
                "patentes_activas": patentes,
                "volumen_total_m3": volumen_total,
                "_gold_timestamp": _now_utc_iso(),
            }
        ]
    )
    schemas.validate(df, schemas.GOLD_KPI_ENTREGAS_SCHEMA, name="gold_kpi_entregas")
    return df


def compute_kpi_por_commerce(viajes: pd.DataFrame) -> pd.DataFrame:
    """KPI agrupado por cliente (commerce)."""
    grouped = (
        viajes.groupby("commerce")
        .agg(
            total_viajes=("suborden", "count"),
            on_time_count=("entrega_on_time", "sum"),
            pct_on_time=("entrega_on_time", lambda x: round(x.mean() * 100, 2)),
            lead_time_prom_dias=("dias_retraso", lambda x: round(x.mean(), 2)),
            no_entregados=("flag_no_entregado", "sum"),
            pct_no_entregado=("flag_no_entregado", lambda x: round(x.mean() * 100, 2)),
            volumen_total=("volumen", lambda x: round(x.sum(), 4)),
            rutas_unicas=("id_ruta", "nunique"),
            patentes_unicas=("patente", "nunique"),
        )
        .reset_index()
    )
    grouped["_gold_timestamp"] = _now_utc_iso()
    schemas.validate(grouped, schemas.GOLD_KPI_POR_COMMERCE_SCHEMA, name="gold_kpi_por_commerce")
    return grouped


def compute_kpi_por_patente(viajes: pd.DataFrame) -> pd.DataFrame:
    """KPI agrupado por patente (camión)."""
    grouped = (
        viajes.groupby("patente")
        .agg(
            total_entregas=("suborden", "count"),
            on_time_count=("entrega_on_time", "sum"),
            pct_on_time=("entrega_on_time", lambda x: round(x.mean() * 100, 2)),
            retraso_prom_dias=("dias_retraso", lambda x: round(x.mean(), 2)),
            no_entregados=("flag_no_entregado", "sum"),
            commerce_clientes=("commerce", lambda x: ", ".join(sorted(x.unique()))),
            regiones_cubiertas=("region", lambda x: ", ".join(sorted(x.unique()))),
            rutas_asignadas=("id_ruta", "nunique"),
        )
        .reset_index()
        .sort_values("pct_on_time", ascending=False)
        .reset_index(drop=True)
    )
    grouped["_gold_timestamp"] = _now_utc_iso()
    schemas.validate(grouped, schemas.GOLD_KPI_POR_PATENTE_SCHEMA, name="gold_kpi_por_patente")
    return grouped


def compute_kpi_devoluciones(devoluciones: pd.DataFrame) -> pd.DataFrame:
    """KPI de devoluciones agrupado por observación (motivo)."""
    grouped = (
        devoluciones.groupby("observaciones")
        .agg(
            cantidad=("nro_etiqueta", "count"),
            dias_devolucion_prom=(
                "dias_hasta_devolucion",
                lambda x: round(pd.to_numeric(x, errors="coerce").mean(), 1),
            ),
        )
        .reset_index()
        .sort_values("cantidad", ascending=False)
        .reset_index(drop=True)
    )
    total = grouped["cantidad"].sum()
    grouped["pct_del_total"] = round(grouped["cantidad"] / total * 100, 2) if total else 0.0
    grouped["_gold_timestamp"] = _now_utc_iso()
    schemas.validate(grouped, schemas.GOLD_KPI_DEVOLUCIONES_SCHEMA, name="gold_kpi_devoluciones")
    return grouped


def compute_dim_tiempo(viajes: pd.DataFrame) -> pd.DataFrame:
    """Dimensión calendario entre min y max de fecha_pactada."""
    fecha_min = viajes["fecha_pactada"].min()
    fecha_max = viajes["fecha_pactada"].max()
    if pd.isna(fecha_min) or pd.isna(fecha_max):
        log.warning("No hay fechas válidas en fecha_pactada; dim_tiempo queda vacía.")
        return pd.DataFrame(
            columns=[
                "fecha",
                "anio",
                "mes",
                "nombre_mes",
                "dia",
                "dia_semana",
                "nombre_dia",
                "semana_anio",
                "trimestre",
                "es_fin_semana",
                "anio_mes",
            ]
        )

    fechas = pd.date_range(start=fecha_min, end=fecha_max, freq="D")
    df = pd.DataFrame(
        {
            "fecha": fechas.strftime("%Y-%m-%d"),
            "anio": fechas.year.astype("int64"),
            "mes": fechas.month.astype("int64"),
            "nombre_mes": fechas.strftime("%B"),
            "dia": fechas.day.astype("int64"),
            "dia_semana": fechas.dayofweek.astype("int64"),
            "nombre_dia": fechas.strftime("%A"),
            "semana_anio": fechas.isocalendar().week.values.astype("int64"),
            "trimestre": fechas.quarter.astype("int64"),
            "es_fin_semana": (fechas.dayofweek >= 5).astype(int),
            "anio_mes": fechas.strftime("%Y-%m"),
        }
    )
    schemas.validate(df, schemas.GOLD_DIM_TIEMPO_SCHEMA, name="gold_dim_tiempo")
    return df


def compute_fact_viajes(viajes: pd.DataFrame) -> pd.DataFrame:
    """Tabla de hechos: 1 fila por viaje, lista para modelo estrella."""
    cols = [c for c in FACT_VIAJES_COLUMNS if c in viajes.columns]
    fact = viajes[cols].copy()
    fact["fecha_key"] = viajes["fecha_pactada"].dt.strftime("%Y-%m-%d")
    fact["_gold_timestamp"] = _now_utc_iso()
    schemas.validate(fact, schemas.GOLD_FACT_VIAJES_SCHEMA, name="gold_fact_viajes")
    return fact


def _read_silver_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        msg = f"Falta el parquet Silver esperado en {path}. Corre transporte.silver antes."
        raise FileNotFoundError(msg)
    log.info("Leyendo %s", path)
    df = pd.read_parquet(path, engine="pyarrow")
    log.info("  %s filas", len(df))
    return df


def _write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, engine="pyarrow", index=False)
    log.info("  parquet -> %s (%s filas)", path, len(df))


def _write_csv_for_bi(df: pd.DataFrame, path: Path) -> None:
    """CSV con UTF-8 BOM para que Excel y Power BI lean acentos correctamente."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    log.info("  csv     -> %s (%s filas)", path, len(df))


def goldify_all(
    input_dir: Path = DEFAULT_DIR,
    output_dir: Path = DEFAULT_DIR,
    exports_dir: Path | None = DEFAULT_EXPORTS_DIR,
) -> dict[str, Path]:
    """Calcula y persiste las 6 tablas Gold en parquet (+ CSVs si exports_dir)."""
    log.info(
        "Gold transform | input_dir=%s | output_dir=%s | exports_dir=%s",
        input_dir,
        output_dir,
        exports_dir,
    )
    viajes = _read_silver_parquet(input_dir / INPUT_VIAJES)
    devoluciones = _read_silver_parquet(input_dir / INPUT_DEVOLUCIONES)

    tables = {
        "gold_kpi_entregas": compute_kpi_entregas(viajes, devoluciones),
        "gold_kpi_por_commerce": compute_kpi_por_commerce(viajes),
        "gold_kpi_por_patente": compute_kpi_por_patente(viajes),
        "gold_kpi_devoluciones": compute_kpi_devoluciones(devoluciones),
        "gold_dim_tiempo": compute_dim_tiempo(viajes),
        "gold_fact_viajes": compute_fact_viajes(viajes),
    }

    parquet_paths: dict[str, Path] = {}
    for name in GOLD_TABLES_ORDER:
        df = tables[name]
        parquet_path = output_dir / f"{name}.parquet"
        _write_parquet(df, parquet_path)
        parquet_paths[name] = parquet_path
        if exports_dir is not None:
            _write_csv_for_bi(df, exports_dir / f"{name}.csv")

    return parquet_paths


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="transporte.gold",
        description="Capa Gold: KPIs operativos y modelo dimensional para BI.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_DIR,
        help=f"Directorio con parquets Silver (default: {DEFAULT_DIR}).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_DIR,
        help=f"Directorio donde escribir parquets Gold (default: {DEFAULT_DIR}).",
    )
    parser.add_argument(
        "--exports-dir",
        type=Path,
        default=DEFAULT_EXPORTS_DIR,
        help=(
            f"Directorio para los CSV exportados a Power BI "
            f"(default: {DEFAULT_EXPORTS_DIR}). Usar --no-exports para saltarlo."
        ),
    )
    parser.add_argument(
        "--no-exports",
        action="store_true",
        help="No genera los CSV de Power BI (solo parquets).",
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
    exports_dir = None if args.no_exports else args.exports_dir
    outputs = goldify_all(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        exports_dir=exports_dir,
    )
    log.info("Gold transform OK: %s tablas", len(outputs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
