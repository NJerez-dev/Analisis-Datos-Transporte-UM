"""Tests para `transporte.gold`.

Encadena bronze -> silver -> gold sobre la muestra anonimizada y verifica
estructura de tablas, KPIs calculados y consistencia con los inputs.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from transporte import bronze, gold, silver

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE = REPO_ROOT / "data" / "sample" / "transporte_um_sample.xlsx"


@pytest.fixture(scope="module")
def silver_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Corre bronze + silver y deja los parquets Silver listos para gold."""
    bronze_out = tmp_path_factory.mktemp("bronze")
    silver_out = tmp_path_factory.mktemp("silver")
    bronze.ingest_all(input_path=SAMPLE, output_dir=bronze_out)
    silver.silverize_all(input_dir=bronze_out, output_dir=silver_out)
    return silver_out


@pytest.fixture(scope="module")
def gold_outputs(silver_dir: Path, tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    out = tmp_path_factory.mktemp("gold")
    return gold.goldify_all(input_dir=silver_dir, output_dir=out, exports_dir=None)


@pytest.fixture(scope="module")
def viajes_silver(silver_dir: Path) -> pd.DataFrame:
    return pd.read_parquet(silver_dir / silver.OUTPUT_VIAJES)


@pytest.fixture(scope="module")
def devoluciones_silver(silver_dir: Path) -> pd.DataFrame:
    return pd.read_parquet(silver_dir / silver.OUTPUT_DEVOLUCIONES)


def test_goldify_all_produces_six_tables(gold_outputs: dict[str, Path]) -> None:
    assert set(gold_outputs.keys()) == set(gold.GOLD_TABLES_ORDER)
    for path in gold_outputs.values():
        assert path.exists(), f"Falta parquet: {path}"


def test_kpi_entregas_es_una_fila(
    viajes_silver: pd.DataFrame, devoluciones_silver: pd.DataFrame
) -> None:
    df = gold.compute_kpi_entregas(viajes_silver, devoluciones_silver)
    assert len(df) == 1
    expected = {
        "total_viajes",
        "viajes_terminados",
        "viajes_on_time",
        "pct_on_time_delivery",
        "pct_no_entregado",
        "lead_time_dias_prom",
        "total_devoluciones",
        "tasa_devolucion_pct",
        "rutas_unicas",
        "patentes_activas",
        "volumen_total_m3",
    }
    assert expected.issubset(set(df.columns))


def test_kpi_entregas_total_viajes_coincide(
    viajes_silver: pd.DataFrame, devoluciones_silver: pd.DataFrame
) -> None:
    df = gold.compute_kpi_entregas(viajes_silver, devoluciones_silver)
    assert df.iloc[0]["total_viajes"] == len(viajes_silver)
    assert df.iloc[0]["total_devoluciones"] == len(devoluciones_silver)


def test_kpi_por_commerce_no_pierde_filas(viajes_silver: pd.DataFrame) -> None:
    df = gold.compute_kpi_por_commerce(viajes_silver)
    assert df["total_viajes"].sum() == len(viajes_silver)
    assert (df["pct_on_time"] >= 0).all()
    assert (df["pct_on_time"] <= 100).all()


def test_kpi_por_patente_ordenado_por_pct_on_time_desc(viajes_silver: pd.DataFrame) -> None:
    df = gold.compute_kpi_por_patente(viajes_silver)
    assert df["pct_on_time"].is_monotonic_decreasing or len(df) <= 1


def test_kpi_devoluciones_pct_suma_100(devoluciones_silver: pd.DataFrame) -> None:
    df = gold.compute_kpi_devoluciones(devoluciones_silver)
    if len(df) > 0:
        assert abs(df["pct_del_total"].sum() - 100) <= 0.5


def test_dim_tiempo_columnas_esperadas(viajes_silver: pd.DataFrame) -> None:
    df = gold.compute_dim_tiempo(viajes_silver)
    expected = {
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
    }
    assert set(df.columns) == expected


def test_fact_viajes_misma_cantidad_que_silver(viajes_silver: pd.DataFrame) -> None:
    df = gold.compute_fact_viajes(viajes_silver)
    assert len(df) == len(viajes_silver)
    assert "fecha_key" in df.columns
    assert df["fecha_key"].str.match(r"^\d{4}-\d{2}-\d{2}$|^$").all()


def test_goldify_all_exports_csvs_when_dir_provided(silver_dir: Path, tmp_path: Path) -> None:
    parquet_dir = tmp_path / "parquet"
    exports_dir = tmp_path / "exports"
    gold.goldify_all(input_dir=silver_dir, output_dir=parquet_dir, exports_dir=exports_dir)
    for name in gold.GOLD_TABLES_ORDER:
        assert (parquet_dir / f"{name}.parquet").exists()
        assert (exports_dir / f"{name}.csv").exists()


def test_goldify_all_skips_csvs_when_exports_none(silver_dir: Path, tmp_path: Path) -> None:
    gold.goldify_all(input_dir=silver_dir, output_dir=tmp_path, exports_dir=None)
    csvs = list(tmp_path.glob("*.csv"))
    assert csvs == []


def test_goldify_missing_silver_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        gold.goldify_all(input_dir=tmp_path, output_dir=tmp_path, exports_dir=None)
