"""Tests para las queries en `sql/analysis/`.

Estas queries son **exploratorias** (no producen tablas Gold), por lo que
los tests verifican estructura y propiedades de window functions, no
equivalencia con una versión pandas.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from transporte import bronze, silver
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
def sql_params(silver_dir: Path) -> dict[str, str]:
    return {"silver_dir": silver_dir_for_sql(silver_dir)}


def test_ranking_patentes_dense_rank_starts_at_1(sql_params: dict[str, str]) -> None:
    df = run_query("sql/analysis/ranking_patentes.sql", params=sql_params)
    assert len(df) > 0
    assert df["rank_general"].min() == 1
    assert df["row_num"].is_unique
    assert df["row_num"].min() == 1
    assert df["row_num"].max() == len(df)


def test_ranking_patentes_dense_rank_no_gaps(sql_params: dict[str, str]) -> None:
    """DENSE_RANK no salta valores: si hay rangos {1, 2, 3}, no aparece {1, 2, 4}."""
    df = run_query("sql/analysis/ranking_patentes.sql", params=sql_params)
    ranks = sorted(df["rank_general"].unique().tolist())
    expected_no_gaps = list(range(1, max(ranks) + 1))
    assert ranks == expected_no_gaps


def test_top_motivos_por_patente_at_most_2_per_patente(sql_params: dict[str, str]) -> None:
    df = run_query("sql/analysis/top_motivos_por_patente.sql", params=sql_params)
    counts = df.groupby("patente").size()
    assert (counts <= 2).all()
    assert df["rk_motivo"].max() <= 2


def test_top_motivos_por_patente_rk_is_monotonic_per_group(
    sql_params: dict[str, str],
) -> None:
    df = run_query("sql/analysis/top_motivos_por_patente.sql", params=sql_params)
    for _patente, group in df.groupby("patente"):
        cantidades = group.sort_values("rk_motivo")["cantidad"].tolist()
        assert cantidades == sorted(cantidades, reverse=True)


def test_analysis_queries_filter_null_motivos(sql_params: dict[str, str]) -> None:
    df = run_query("sql/analysis/top_motivos_por_patente.sql", params=sql_params)
    assert df["motivo_no_entrega"].notna().all()
    assert (df["motivo_no_entrega"].str.strip() != "").all()


def test_explain_query_returns_plan(sql_params: dict[str, str]) -> None:
    """EXPLAIN debe correr sobre cualquier query y devolver el plan textual."""
    import duckdb

    sql = Path("sql/analysis/ranking_patentes.sql").read_text(encoding="utf-8").format(**sql_params)
    con = duckdb.connect(database=":memory:")
    try:
        plan_rows = con.execute(f"EXPLAIN {sql}").fetchall()
        plan_text = "\n".join(str(r) for r in plan_rows)
        assert "WINDOW" in plan_text or "window" in plan_text.lower()
        assert "AGGREGATE" in plan_text or "GROUP" in plan_text.upper()
    finally:
        con.close()
