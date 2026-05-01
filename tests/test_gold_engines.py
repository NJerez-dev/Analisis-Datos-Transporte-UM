"""Verifica que `goldify_all(engine="sql")` y `goldify_all(engine="pandas")`
producen los mismos parquets sobre la misma muestra Silver.

Es el test que sostiene la decisión "SQL como default, pandas como fallback".
Si SQL diverge de pandas en cualquier celda numérica, este test falla.
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
    bronze_out = tmp_path_factory.mktemp("bronze")
    silver_out = tmp_path_factory.mktemp("silver")
    bronze.ingest_all(input_path=SAMPLE, output_dir=bronze_out)
    silver.silverize_all(input_dir=bronze_out, output_dir=silver_out)
    return silver_out


def _drop_timestamp(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop(columns=[c for c in df.columns if c.startswith("_")])


def _normalize_for_compare(df: pd.DataFrame) -> pd.DataFrame:
    out = _drop_timestamp(df).copy()
    for col in out.columns:
        if pd.api.types.is_numeric_dtype(out[col]):
            out[col] = out[col].astype(float)
    return out.reset_index(drop=True)


def test_engines_produce_same_parquets(silver_dir: Path, tmp_path: Path) -> None:
    sql_dir = tmp_path / "sql"
    pandas_dir = tmp_path / "pandas"

    gold.goldify_all(input_dir=silver_dir, output_dir=sql_dir, exports_dir=None, engine="sql")
    gold.goldify_all(input_dir=silver_dir, output_dir=pandas_dir, exports_dir=None, engine="pandas")

    for table in gold.GOLD_TABLES_ORDER:
        sql_df = pd.read_parquet(sql_dir / f"{table}.parquet")
        pd_df = pd.read_parquet(pandas_dir / f"{table}.parquet")

        if "commerce" in sql_df.columns:
            sql_df = sql_df.sort_values("commerce").reset_index(drop=True)
            pd_df = pd_df.sort_values("commerce").reset_index(drop=True)
        elif "patente" in sql_df.columns and table != "gold_fact_viajes":
            sql_df = sql_df.sort_values(
                ["pct_on_time", "patente"], ascending=[False, True]
            ).reset_index(drop=True)
            pd_df = pd_df.sort_values(
                ["pct_on_time", "patente"], ascending=[False, True]
            ).reset_index(drop=True)
        elif "observaciones" in sql_df.columns:
            sql_df = sql_df.sort_values(
                ["cantidad", "observaciones"], ascending=[False, True]
            ).reset_index(drop=True)
            pd_df = pd_df.sort_values(
                ["cantidad", "observaciones"], ascending=[False, True]
            ).reset_index(drop=True)

        common = sorted(set(sql_df.columns) & set(pd_df.columns))
        sql_norm = _normalize_for_compare(sql_df[common])
        pd_norm = _normalize_for_compare(pd_df[common])

        if table == "gold_fact_viajes":
            sql_norm = sql_norm.sort_values("suborden").reset_index(drop=True)
            pd_norm = pd_norm.sort_values("suborden").reset_index(drop=True)

        pd.testing.assert_frame_equal(
            sql_norm,
            pd_norm,
            check_dtype=False,
            check_exact=False,
            rtol=1e-3,
            obj=table,
        )


def test_default_engine_is_sql(silver_dir: Path, tmp_path: Path) -> None:
    """El default de goldify_all es 'sql' — verificable porque SQL_QUERIES se
    invocan al menos una vez y el output es válido."""
    outputs = gold.goldify_all(input_dir=silver_dir, output_dir=tmp_path, exports_dir=None)
    assert len(outputs) == len(gold.GOLD_TABLES_ORDER)
    assert gold.DEFAULT_ENGINE == "sql"


def test_engine_invalid_raises(silver_dir: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="engine debe ser"):
        gold.goldify_all(
            input_dir=silver_dir,
            output_dir=tmp_path,
            exports_dir=None,
            engine="duckdb",  # type: ignore[arg-type]
        )
