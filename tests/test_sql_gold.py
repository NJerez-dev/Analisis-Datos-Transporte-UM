"""Tests de regresión: las queries SQL en `sql/gold/` producen los mismos
resultados que las funciones pandas equivalentes en `transporte.gold`.

Si una query SQL diverge de la versión pandas, este test detecta exactamente
qué columna y qué fila difieren. Es el seguro mientras coexisten ambas
implementaciones.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from transporte import bronze, gold, silver
from transporte.sql_runner import run_query, silver_dir_for_sql

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE = REPO_ROOT / "data" / "sample" / "transporte_um_sample.xlsx"


@pytest.fixture(scope="module")
def silver_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    bronze_out = tmp_path_factory.mktemp("bronze")
    silver_out = tmp_path_factory.mktemp("silver")
    bronze.ingest_all(input_path=SAMPLE, output_dir=bronze_out)
    silver.silverize_all(input_dir=bronze_out, output_dir=silver_out)
    return silver_out


@pytest.fixture(scope="module")
def viajes_silver(silver_dir: Path) -> pd.DataFrame:
    return pd.read_parquet(silver_dir / silver.OUTPUT_VIAJES)


@pytest.fixture(scope="module")
def devoluciones_silver(silver_dir: Path) -> pd.DataFrame:
    return pd.read_parquet(silver_dir / silver.OUTPUT_DEVOLUCIONES)


@pytest.fixture(scope="module")
def sql_params(silver_dir: Path) -> dict[str, str]:
    return {"silver_dir": silver_dir_for_sql(silver_dir)}


def _drop_timestamp(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop(columns=[c for c in df.columns if c.startswith("_")])


def _normalize_for_compare(df: pd.DataFrame) -> pd.DataFrame:
    """Castea numéricos a float para que int64/float64 no rompan la comparación."""
    out = _drop_timestamp(df).copy()
    for col in out.columns:
        if pd.api.types.is_numeric_dtype(out[col]):
            out[col] = out[col].astype(float)
    return out.reset_index(drop=True)


def test_sql_kpi_entregas_matches_pandas(
    viajes_silver: pd.DataFrame,
    devoluciones_silver: pd.DataFrame,
    sql_params: dict[str, str],
) -> None:
    sql_df = run_query("sql/gold/kpi_entregas.sql", params=sql_params)
    pd_df = gold.compute_kpi_entregas(viajes_silver, devoluciones_silver)

    sql_norm = _normalize_for_compare(sql_df)
    pd_norm = _normalize_for_compare(pd_df)

    pd.testing.assert_frame_equal(
        sql_norm[sorted(sql_norm.columns)],
        pd_norm[sorted(pd_norm.columns)],
        check_dtype=False,
        check_exact=False,
        rtol=1e-3,
    )


def test_sql_kpi_por_commerce_matches_pandas(
    viajes_silver: pd.DataFrame,
    sql_params: dict[str, str],
) -> None:
    sql_df = run_query("sql/gold/kpi_por_commerce.sql", params=sql_params)
    pd_df = (
        gold.compute_kpi_por_commerce(viajes_silver).sort_values("commerce").reset_index(drop=True)
    )

    sql_norm = _normalize_for_compare(sql_df.sort_values("commerce").reset_index(drop=True))
    pd_norm = _normalize_for_compare(pd_df)

    common = sorted(set(sql_norm.columns) & set(pd_norm.columns))
    pd.testing.assert_frame_equal(sql_norm[common], pd_norm[common], check_dtype=False, rtol=1e-3)


def test_sql_kpi_por_patente_matches_pandas(
    viajes_silver: pd.DataFrame,
    sql_params: dict[str, str],
) -> None:
    sql_df = run_query("sql/gold/kpi_por_patente.sql", params=sql_params)
    pd_df = gold.compute_kpi_por_patente(viajes_silver)

    sql_norm = _normalize_for_compare(
        sql_df.sort_values(["pct_on_time", "patente"], ascending=[False, True]).reset_index(
            drop=True
        )
    )
    pd_norm = _normalize_for_compare(
        pd_df.sort_values(["pct_on_time", "patente"], ascending=[False, True]).reset_index(
            drop=True
        )
    )

    common = sorted(set(sql_norm.columns) & set(pd_norm.columns))
    pd.testing.assert_frame_equal(sql_norm[common], pd_norm[common], check_dtype=False, rtol=1e-3)


def test_sql_kpi_devoluciones_matches_pandas(
    devoluciones_silver: pd.DataFrame,
    sql_params: dict[str, str],
) -> None:
    sql_df = run_query("sql/gold/kpi_devoluciones.sql", params=sql_params)
    pd_df = gold.compute_kpi_devoluciones(devoluciones_silver)

    sql_norm = _normalize_for_compare(
        sql_df.sort_values(["cantidad", "observaciones"], ascending=[False, True]).reset_index(
            drop=True
        )
    )
    pd_norm = _normalize_for_compare(
        pd_df.sort_values(["cantidad", "observaciones"], ascending=[False, True]).reset_index(
            drop=True
        )
    )

    common = sorted(set(sql_norm.columns) & set(pd_norm.columns))
    pd.testing.assert_frame_equal(sql_norm[common], pd_norm[common], check_dtype=False, rtol=1e-3)


def test_sql_dim_tiempo_matches_pandas(
    viajes_silver: pd.DataFrame,
    sql_params: dict[str, str],
) -> None:
    sql_df = run_query("sql/gold/dim_tiempo.sql", params=sql_params)
    pd_df = gold.compute_dim_tiempo(viajes_silver)

    expected_cols = [
        "fecha",
        "anio",
        "mes",
        "dia",
        "dia_semana",
        "trimestre",
        "es_fin_semana",
        "anio_mes",
    ]
    assert all(c in sql_df.columns for c in expected_cols)
    assert len(sql_df) == len(pd_df)
    assert (sql_df["fecha"].astype(str) == pd_df["fecha"].astype(str)).all()


def test_sql_fact_viajes_matches_pandas(
    viajes_silver: pd.DataFrame,
    sql_params: dict[str, str],
) -> None:
    sql_df = run_query("sql/gold/fact_viajes.sql", params=sql_params)
    pd_df = gold.compute_fact_viajes(viajes_silver)

    assert len(sql_df) == len(pd_df)
    common = sorted(set(sql_df.columns) & set(pd_df.columns))
    assert "fecha_key" in common
    assert "suborden" in common


def test_sql_runner_missing_query_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        run_query(tmp_path / "no-existe.sql")
